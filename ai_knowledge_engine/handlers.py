#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import logging
import os
import sys
import traceback
import zipfile
from typing import Any, Callable, Dict, List, Optional, Tuple

import boto3
import pendulum
from graphene import ResolveInfo
from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from neo4j_graph_connector import Neo4jConnector
from redis_stack_connector import RedisStackConnector
from silvaengine_dynamodb_base import (
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility

from .models import (
    DataSourceModel,
    DocumentModel,
    DocumentProcessEntityModel,
    DocumentProcessTaskModel,
    KnowledgeGraphMetadataModel,
    RequestModel,
)
from .types import (
    DataSourceListType,
    DataSourceType,
    DataViewType,
    DocumentListType,
    DocumentProcessEntityListType,
    DocumentProcessEntityType,
    DocumentProcessTaskListType,
    DocumentProcessTaskType,
    DocumentType,
    KnowledgeGraphMetadataListType,
    KnowledgeGraphMetadataType,
    KnowledgeRagType,
    RequestListType,
    RequestType,
)


class SchemaRetrievalError(Exception):
    """Raised when the graph schema cannot be retrieved."""

    pass


class InsufficientDetailsError(Exception):
    """Raised when insufficient details are provided in the user query."""

    pass


openai_client = None
openai_model = None
neo4j_connector = None
redis_stack_connector = None
redis_index_config = None
neo4j_database = None
graph_schema = None
system_contents = None
adaptor_bucket_name = None
adaptor_zip_path = None
adaptor_extract_path = None
aws_s3 = None


def handlers_init(logger: logging.Logger, **setting: Dict[str, Any]) -> None:
    try:
        global aws_s3
        global openai_client, openai_model
        global neo4j_connector, neo4j_database, graph_schema, system_contents
        global redis_stack_connector, redis_index_config
        global adaptor_bucket_name, adaptor_zip_path, adaptor_extract_path

        _initialize_aws_services(setting)
        _initialize_openai_client(setting)
        _initialize_neo4j(logger, setting)
        _initialize_redis_stack(logger, setting)
        _setup_function_paths(setting)

    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


def _initialize_aws_services(setting: Dict[str, Any]) -> None:
    global aws_s3
    if all(
        setting.get(k)
        for k in ["region_name", "aws_access_key_id", "aws_secret_access_key"]
    ):
        aws_credentials = {
            "region_name": setting["region_name"],
            "aws_access_key_id": setting["aws_access_key_id"],
            "aws_secret_access_key": setting["aws_secret_access_key"],
        }
    else:
        aws_credentials = {}

    aws_s3 = boto3.client("s3", **aws_credentials)


def _initialize_openai_client(setting: Dict[str, Any]) -> None:
    global openai_client, openai_model

    if "openai_api_key" in setting:
        openai_client = OpenAI(api_key=setting["openai_api_key"])
    if "openai_model" in setting:
        openai_model = setting["openai_model"]


def _initialize_neo4j(logger: logging.Logger, setting: Dict[str, Any]) -> None:
    global neo4j_connector, neo4j_database, graph_schema, system_contents
    if (
        "neo4j_uri" in setting
        and "neo4j_username" in setting
        and "neo4j_password" in setting
    ):
        neo4j_connector = Neo4jConnector(
            logger,
            **{
                "neo4j_uri": setting["neo4j_uri"],
                "neo4j_username": setting["neo4j_username"],
                "neo4j_password": setting["neo4j_password"],
            },
        )
    if "neo4j_database" in setting:
        neo4j_database = setting["neo4j_database"]
        graph_schema = neo4j_connector.get_graph_schema(database=neo4j_database)

    if "system_contents" in setting:
        system_contents = setting["system_contents"]


def _initialize_redis_stack(logger: logging.Logger, setting: Dict[str, Any]) -> None:
    global redis_stack_connector, redis_index_config
    if (
        "openai_api_key" in setting
        and "REDIS_HOST" in setting
        and "REDIS_PORT" in setting
        and "REDIS_PASSWORD" in setting
        and "EMBEDDING_MODEL" in setting
    ):
        redis_stack_connector = RedisStackConnector(
            logger,
            **{
                "openai_api_key": setting["openai_api_key"],
                "REDIS_HOST": setting["REDIS_HOST"],
                "REDIS_PORT": setting["REDIS_PORT"],
                "REDIS_PASSWORD": setting["REDIS_PASSWORD"],
                "EMBEDDING_MODEL": setting["EMBEDDING_MODEL"],
            },
        )
    if "redis_index_config" in setting:
        redis_index_config = setting["redis_index_config"]


def _setup_function_paths(setting: Dict[str, Any]) -> None:
    global adaptor_bucket_name, adaptor_zip_path, adaptor_extract_path
    adaptor_bucket_name = setting.get("adaptor_bucket_name")
    adaptor_zip_path = setting.get("adaptor_zip_path", "/tmp/adaptor_zips")
    adaptor_extract_path = setting.get("adaptor_extract_path", "/tmp/adaptors")
    os.makedirs(adaptor_zip_path, exist_ok=True)
    os.makedirs(adaptor_extract_path, exist_ok=True)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_document(document_source: str, document_uuid: str) -> DocumentModel:
    return DocumentModel.get(document_source, document_uuid)


def get_document_count(document_source: str, document_uuid: str) -> int:
    return DocumentModel.count(
        document_source, DocumentModel.document_uuid == document_uuid
    )


def get_document_type(info: ResolveInfo, document: DocumentModel) -> DocumentType:
    try:
        document_source = _get_data_source(
            document.document_type, document.document_type
        )
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    document = document.__dict__["attribute_values"]
    document["document_source"] = document_source
    document.pop("document_type")
    return DocumentType(**Utility.json_loads(Utility.json_dumps(document)))


def resolve_document_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentType:
    return get_document_type(
        info, get_document(kwargs.get("document_source"), kwargs.get("document_uuid"))
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["document_source", "document_uuid", "document_external_id"],
    list_type_class=DocumentListType,
    type_funct=get_document_type,
)
def resolve_document_list_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    document_source = kwargs.get("document_source")
    document_external_id = kwargs.get("document_external_id")
    document_types = kwargs.get("document_types")
    document_title = kwargs.get("document_title")
    document_content = kwargs.get("document_content")
    statuses = kwargs.get("statuses")

    args = []
    inquiry_funct = DocumentModel.scan
    count_funct = DocumentModel.count
    if document_source:
        args = [document_source, None]
        inquiry_funct = DocumentModel.query
        if document_external_id:
            inquiry_funct = DocumentModel.document_external_id_index.query
            args[1] = DocumentModel.document_external_id == document_external_id
            count_funct = DocumentModel.document_external_id_index.count

    the_filters = None  # We can add filters for the query.
    if document_types:
        the_filters &= DocumentModel.document_type.is_in(*document_types)
    if document_title:
        the_filters &= DocumentModel.document_title.contains(document_title)
    if document_content:
        the_filters &= DocumentModel.document_content.contains(document_content)
    if statuses:
        the_filters &= DocumentModel.status.is_in(*statuses)

    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "document_source",
        "range_key": "document_uuid",
    },
    model_funct=get_document,
    count_funct=get_document_count,
    type_funct=get_document_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_document_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentType:
    document_source = kwargs.get("document_source")
    document_uuid = kwargs.get("document_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "document_external_id": kwargs["document_external_id"],
            "document_type": kwargs["document_type"],
            "document_title": kwargs["document_title"],
            "document_content": kwargs["document_content"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if kwargs.get("chunk_index"):
            cols["chunk_index"] = kwargs["chunk_index"]
        if kwargs.get("title_embedding") is not None:
            cols["title_embedding"] = kwargs["title_embedding"]
        if kwargs.get("content_embedding") is not None:
            cols["content_embedding"] = kwargs["content_embedding"]
        DocumentModel(
            document_source,
            document_uuid,
            **cols,
        ).save()
        return

    document = kwargs.get("entity")
    actions = [
        DocumentModel.updated_by.set(kwargs["updated_by"]),
        DocumentModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to DocumentModel attributes
    field_map = {
        "document_title": DocumentModel.document_title,
        "document_content": DocumentModel.document_content,
        "title_embedding": DocumentModel.title_embedding,
        "content_embedding": DocumentModel.content_embedding,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the session
    document.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "document_source",
        "range_key": "document_uuid",
    },
    model_funct=get_document,
)
def delete_document_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_document_process_task(
    document_source: str, process_task_uuid: str
) -> DocumentProcessTaskModel:
    return DocumentProcessTaskModel.get(document_source, process_task_uuid)


def get_document_process_task_count(
    document_source: str, process_task_uuid: str
) -> int:
    return DocumentProcessTaskModel.count(
        document_source, DocumentProcessTaskModel.process_task_uuid == process_task_uuid
    )


def _get_document_process_task(
    document_source: str, process_task_uuid: str
) -> Dict[str, Any]:
    document_process_task = get_document_process_task(
        document_source, process_task_uuid
    )
    return {
        "document_source": _get_data_source(
            document_process_task.document_type, document_source
        ),
        "process_task_uuid": document_process_task.process_task_uuid,
        "process_status": document_process_task.process_status,
        "process_note": document_process_task.process_note,
        "cut_time": document_process_task.cut_time,
        "start_time": document_process_task.start_time,
        "end_time": document_process_task.end_time,
    }


def get_document_process_task_type(
    info: ResolveInfo, document_process_task: DocumentProcessTaskModel
) -> DocumentProcessTaskType:
    try:
        document_source = _get_data_source(
            document_process_task.document_type,
            document_process_task.document_source,
        )
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    document_process_task = document_process_task.__dict__["attribute_values"]
    document_process_task["document_source"] = document_source
    document_process_task.pop("document_type")
    return DocumentProcessTaskType(
        **Utility.json_loads(Utility.json_dumps(document_process_task))
    )


def resolve_document_process_task_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessTaskType:
    return get_document_process_task_type(
        info,
        get_document_process_task(
            kwargs.get("document_source"), kwargs.get("process_task_uuid")
        ),
    )


@resolve_list_decorator(
    attributes_to_get=["document_type", "process_task_uuid"],
    list_type_class=DocumentProcessTaskListType,
    type_funct=get_document_process_task_type,
)
def resolve_document_process_task_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    document_source = kwargs.get("document_source")
    document_types = kwargs.get("document_types")
    process_statuses = kwargs.get("process_statuses")
    args = []
    inquiry_funct = DocumentProcessTaskModel.scan
    count_funct = DocumentProcessTaskModel.count
    if document_source:
        args = [document_source, None]
        inquiry_funct = DocumentProcessTaskModel.query

    the_filters = None  # We can add filters for the query.
    if document_types:
        the_filters &= DocumentProcessTaskModel.document_type.is_in(*document_types)
    if process_statuses:
        the_filters &= DocumentProcessTaskModel.process_status.is_in(*process_statuses)

    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "document_type",
        "range_key": "process_task_uuid",
    },
    model_funct=get_document_process_task,
    count_funct=get_document_process_task_count,
    type_funct=get_document_process_task_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_document_process_task_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessTaskType:
    document_source = kwargs.get("document_source")
    process_task_uuid = kwargs.get("process_task_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "document_type": kwargs["document_type"],
            "start_time": pendulum.now("UTC"),
        }
        if kwargs.get("process_status") is not None:
            cols["process_status"] = kwargs["process_status"]
        DocumentProcessTaskModel(document_source, process_task_uuid, **cols).save()
        return

    document_process_task = kwargs.get("entity")
    actions = [
        DocumentProcessTaskModel.end_time.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to document_process_task attributes
    field_map = {
        "process_status": DocumentProcessTaskModel.process_status,
        "process_note": DocumentProcessTaskModel.process_note,
        "cut_time": DocumentProcessTaskModel.cut_time,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the document_process_task
    document_process_task.update(actions=actions)

    return


@delete_decorator(
    keys={
        "hash_key": "document_type",
        "range_key": "process_task_uuid",
    },
    model_funct=get_document_process_task,
)
def delete_document_process_task_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_document_process_entity(
    process_task_uuid: str, document_entity_uuid: str
) -> DocumentProcessEntityModel:
    return DocumentProcessEntityModel.get(process_task_uuid, document_entity_uuid)


def get_document_process_entity_count(
    process_task_uuid: str, document_entity_uuid: str
) -> int:
    return DocumentProcessEntityModel.count(
        process_task_uuid,
        DocumentProcessEntityModel.document_entity_uuid == document_entity_uuid,
    )


def get_document_process_entity_type(
    info: ResolveInfo, document_process_entity: DocumentProcessEntityModel
) -> DocumentProcessEntityType:
    try:
        document_process_task = _get_document_process_task(
            document_process_entity.document_source,
            document_process_entity.process_task_uuid,
        )
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    document_process_entity = document_process_entity.__dict__["attribute_values"]
    document_process_entity["document_process_task"] = document_process_task
    document_process_entity.pop("document_source")
    document_process_entity.pop("process_task_uuid")
    return DocumentProcessEntityType(
        **Utility.json_loads(Utility.json_dumps(document_process_entity))
    )


def resolve_document_process_entity_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessEntityType:
    return get_document_process_entity_type(
        info,
        get_document_process_entity(
            kwargs.get("process_task_uuid"), kwargs.get("document_entity_uuid")
        ),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "process_task_uuid",
        "document_entity_uuid",
        "document_external_id",
    ],
    list_type_class=DocumentProcessEntityListType,
    type_funct=get_document_process_entity_type,
)
def resolve_document_process_entity_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    process_task_uuid = kwargs.get("process_task_uuid")
    document_external_id = kwargs.get("document_external_id")
    document_sources = kwargs.get("document_sources")
    document_version = kwargs.get("document_version")

    args = []
    inquiry_funct = DocumentProcessEntityModel.scan
    count_funct = DocumentProcessEntityModel.count
    if process_task_uuid:
        args = [process_task_uuid, None]
        inquiry_funct = DocumentProcessEntityModel.query
        if document_external_id:
            inquiry_funct = DocumentProcessEntityModel.document_external_id_index.query
            args[1] = (
                DocumentProcessEntityModel.document_external_id == document_external_id
            )
            count_funct = DocumentProcessEntityModel.document_external_id_index.count

    the_filters = None  # We can add filters for the query.
    if document_sources:
        the_filters &= DocumentProcessEntityModel.document_source.is_in(
            *document_sources
        )
    if document_version:
        the_filters &= DocumentProcessEntityModel.document_version == document_version
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "process_task_uuid",
        "range_key": "document_entity_uuid",
    },
    model_funct=get_document_process_entity,
    count_funct=get_document_process_entity_count,
    type_funct=get_document_process_entity_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_document_process_entity_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessEntityType:
    process_task_uuid = kwargs.get("process_task_uuid")
    document_entity_uuid = kwargs.get("document_entity_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "document_external_id": kwargs["document_external_id"],
            "document_source": kwargs["document_source"],
            "document_version": kwargs["document_version"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if kwargs.get("logs") is not None:
            cols["logs"] = kwargs["logs"]
        if kwargs.get("status") is not None:
            cols["status"] = kwargs["status"]
        DocumentProcessEntityModel(
            process_task_uuid, document_entity_uuid, **cols
        ).save()
        return

    document_process_entity = kwargs.get("entity")
    actions = [
        DocumentProcessEntityModel.updated_by.set(kwargs["updated_by"]),
        DocumentProcessEntityModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to document_process_entity attributes
    field_map = {
        "document_source": DocumentProcessEntityModel.document_source,
        "document_version": DocumentProcessEntityModel.document_version,
        "logs": DocumentProcessEntityModel.logs,
        "status": DocumentProcessEntityModel.status,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the document_process_entity
    document_process_entity.update(actions=actions)

    return


@delete_decorator(
    keys={
        "hash_key": "process_task_uuid",
        "range_key": "document_entity_uuid",
    },
    model_funct=get_document_process_entity,
)
def delete_document_process_entity_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_knowledge_graph_metadata(
    document_source: str, metadata_version_uuid: str
) -> KnowledgeGraphMetadataModel:
    return KnowledgeGraphMetadataModel.get(document_source, metadata_version_uuid)


def get_knowledge_graph_metadata_count(
    document_source: str, metadata_version_uuid: str
) -> int:
    return KnowledgeGraphMetadataModel.count(
        document_source,
        KnowledgeGraphMetadataModel.metadata_version_uuid == metadata_version_uuid,
    )


def get_knowledge_graph_metadata_type(
    info: ResolveInfo, knowledge_graph_metadata: KnowledgeGraphMetadataModel
) -> KnowledgeGraphMetadataType:
    try:
        document_source = _get_data_source(
            knowledge_graph_metadata.document_type,
            knowledge_graph_metadata.document_source,
        )
        structured_data_views = [
            {
                "data_source": _get_data_source(
                    structured_data_view["data_source_type"],
                    structured_data_view["data_source_name"],
                ),
                "data_view_name": structured_data_view["data_view_name"],
            }
            for structured_data_view in knowledge_graph_metadata.structured_data_views
        ]
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    knowledge_graph_metadata = knowledge_graph_metadata.__dict__["attribute_values"]
    knowledge_graph_metadata["document_source"] = document_source
    knowledge_graph_metadata["structured_data_views"] = structured_data_views
    knowledge_graph_metadata.pop("document_type")
    return KnowledgeGraphMetadataType(
        **Utility.json_loads(Utility.json_dumps(knowledge_graph_metadata))
    )


def resolve_knowledge_graph_metadata_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeGraphMetadataType:
    return get_knowledge_graph_metadata_type(
        info,
        get_knowledge_graph_metadata(
            kwargs.get("document_source"), kwargs.get("metadata_version_uuid")
        ),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["document_source", "metadata_version_uuid"],
    list_type_class=KnowledgeGraphMetadataListType,
    type_funct=get_knowledge_graph_metadata_type,
)
def resolve_knowledge_graph_metadata_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    document_source = kwargs.get("document_source")
    document_types = kwargs.get("document_types")
    status = kwargs.get("status")
    args = []
    inquiry_funct = KnowledgeGraphMetadataModel.scan
    count_funct = KnowledgeGraphMetadataModel.count
    if document_source:
        args = [document_source, None]
        inquiry_funct = KnowledgeGraphMetadataModel.query

    the_filters = None  # We can add filters for the query.
    if document_types:
        the_filters &= KnowledgeGraphMetadataModel.document_type.is_in(*document_types)
    if status:
        the_filters &= KnowledgeGraphMetadataModel.status == status
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "document_source",
        "range_key": "metadata_version_uuid",
    },
    model_funct=get_knowledge_graph_metadata,
    count_funct=get_knowledge_graph_metadata_count,
    type_funct=get_knowledge_graph_metadata_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_knowledge_graph_metadata_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeGraphMetadataType:
    document_source = kwargs.get("document_source")
    metadata_version_uuid = kwargs.get("metadata_version_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "document_type": kwargs["document_type"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if kwargs.get("structured_data_views") is not None:
            cols["structured_data_views"] = kwargs["structured_data_views"]
        if kwargs.get("structured_fields") is not None:
            cols["structured_fields"] = kwargs["structured_fields"]
        if kwargs.get("unstructured_attributes") is not None:
            cols["unstructured_attributes"] = kwargs["unstructured_attributes"]
        if kwargs.get("linkage_rules") is not None:
            cols["linkage_rules"] = kwargs["linkage_rules"]
        if kwargs.get("merge_rule") is not None:
            cols["merge_rule"] = kwargs["merge_rule"]
        if kwargs.get("status") is not None:
            cols["status"] = kwargs["status"]
        KnowledgeGraphMetadataModel(
            document_source,
            metadata_version_uuid,
            **cols,
        ).save()
        return

    knowledge_graph_metadata = kwargs.get("entity")
    actions = [
        KnowledgeGraphMetadataModel.updated_by.set(kwargs["updated_by"]),
        KnowledgeGraphMetadataModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to KnowledgeGraphMetadataModel attributes
    field_map = {
        "structured_data_views": KnowledgeGraphMetadataModel.structured_data_views,
        "structured_fields": KnowledgeGraphMetadataModel.structured_fields,
        "unstructured_attributes": KnowledgeGraphMetadataModel.unstructured_attributes,
        "linkage_rules": KnowledgeGraphMetadataModel.linkage_rules,
        "merge_rule": KnowledgeGraphMetadataModel.merge_rule,
        "status": KnowledgeGraphMetadataModel.status,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the knowledge_graph_metadata
    knowledge_graph_metadata.update(actions=actions)

    return


@delete_decorator(
    keys={
        "hash_key": "document_type",
        "range_key": "metadata_version_uuid",
    },
    model_funct=get_knowledge_graph_metadata,
)
def delete_knowledge_graph_metadata_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_data_source(data_source_type: str, data_source_name: str) -> DataSourceModel:
    return DataSourceModel.get(data_source_type, data_source_name)


def get_data_source_count(data_source_type: str, data_source_name: str) -> int:
    return DataSourceModel.count(
        data_source_type, DataSourceModel.data_source_name == data_source_name
    )


def _get_data_source(data_source_type: str, data_source_name: str) -> DataSourceModel:
    data_source = get_data_source(data_source_type, data_source_name)
    return {
        "data_source_type": data_source_type,
        "data_source_name": data_source_name,
        "module_name": data_source.module_name,
        "class_name": data_source.class_name,
        "configuration": data_source.configuration,
        "data_views": data_source.data_views,
    }


def get_data_source_type(
    info: ResolveInfo, data_source: DataSourceModel
) -> DataSourceType:
    data_source = data_source.__dict__["attribute_values"]
    return DataSourceType(**Utility.json_loads(Utility.json_dumps(data_source)))


def resolve_data_source_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DataSourceType:
    return get_data_source_type(
        info,
        get_data_source(kwargs.get("data_source_type"), kwargs.get("data_source_name")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["data_source_type", "data_source_name"],
    list_type_class=DataSourceListType,
    type_funct=get_data_source_type,
)
def resolve_data_source_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    data_source_type = kwargs.get("data_source_type")
    module_name = kwargs.get("module_name")
    class_name = kwargs.get("class_name")
    args = []
    inquiry_funct = DataSourceModel.scan
    count_funct = DataSourceModel.count
    if data_source_type:
        args = [data_source_type, None]
        inquiry_funct = DataSourceModel.query

    the_filters = None  # We can add filters for the query.
    if module_name:
        the_filters &= DataSourceModel.module_name.contains(module_name)
    if class_name:
        the_filters &= DataSourceModel.class_name.contains(class_name)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "data_source_type",
        "range_key": "data_source_name",
    },
    range_key_required=True,
    model_funct=get_data_source,
    count_funct=get_data_source_count,
    type_funct=get_data_source_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_data_source_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> None:
    data_source_type = kwargs.get("data_source_type")
    data_source_name = kwargs.get("data_source_name")
    if kwargs.get("entity") is None:
        cols = {
            "module_name": kwargs["module_name"],
            "class_name": kwargs["class_name"],
            "configuration": kwargs["configuration"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if kwargs.get("data_views") is not None:
            cols["data_views"] = kwargs["data_views"]
        DataSourceModel(
            data_source_type,
            data_source_name,
            **cols,
        ).save()
        return

    data_source = kwargs.get("entity")
    actions = [
        DataSourceModel.updated_by.set(kwargs["updated_by"]),
        DataSourceModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to DataSourceModel attributes
    field_map = {
        "module_name": DataSourceModel.module_name,
        "class_name": DataSourceModel.class_name,
        "configuration": DataSourceModel.configuration,
        "data_views": DataSourceModel.data_views,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the data_source
    data_source.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "data_source_type",
        "range_key": "data_source_name",
    },
    model_funct=get_data_source,
)
def delete_data_source_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_request(document_source: str, request_uuid: str) -> RequestModel:
    return RequestModel.get(document_source, request_uuid)


def get_request_count(document_source: str, request_uuid: str) -> int:
    return RequestModel.count(
        document_source, RequestModel.request_uuid == request_uuid
    )


def get_request_type(info: ResolveInfo, request: RequestModel) -> RequestType:
    request = request.__dict__["attribute_values"]
    return RequestType(**Utility.json_loads(Utility.json_dumps(request)))


def resolve_request_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> RequestType:
    return get_request_type(
        info,
        get_request(kwargs.get("document_source"), kwargs.get("request_uuid")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["document_source", "request_uuid"],
    list_type_class=RequestListType,
    type_funct=get_request_type,
)
def resolve_request_list_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    document_source = kwargs.get("document_source")
    user_query = kwargs.get("user_query")
    cypher_query = kwargs.get("cypher_query")
    is_similarity_search = kwargs.get("is_similarity_search")

    args = []
    inquiry_funct = RequestModel.scan
    count_funct = RequestModel.count
    if document_source:
        args = [document_source, None]
        inquiry_funct = RequestModel.query

    the_filters = None  # We can add filters for the query.
    if user_query:
        the_filters &= RequestModel.user_query.contains(user_query)
    if cypher_query:
        the_filters &= RequestModel.cypher_query.contains(cypher_query)
    if is_similarity_search:
        the_filters &= RequestModel.is_similarity_search == is_similarity_search
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "document_source",
        "range_key": "request_uuid",
    },
    range_key_required=True,
    model_funct=get_request,
    count_funct=get_request_count,
    type_funct=get_request_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_request_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    document_source = kwargs.get("document_source")
    request_uuid = kwargs.get("request_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "user_query": kwargs["user_query"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if kwargs.get("cypher_query"):
            cols["cypher_query"] = kwargs["cypher_query"]
        if kwargs.get("is_similarity_search"):
            cols["is_similarity_search"] = kwargs["is_similarity_search"]
        if kwargs.get("results"):
            cols["results"] = kwargs["results"]
        if kwargs.get("request_note"):
            cols["request_note"] = kwargs["request_note"]
        RequestModel(
            document_source,
            request_uuid,
            **cols,
        ).save()
        return

    request = kwargs.get("entity")
    actions = [
        RequestModel.updated_by.set(kwargs["updated_by"]),
        RequestModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to RequestModel attributes
    field_map = {
        "cypher_query": RequestModel.cypher_query,
        "is_similarity_search": RequestModel.is_similarity_search,
        "results": RequestModel.results,
        "request_note": RequestModel.request_note,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the request
    request.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "document_source",
        "range_key": "request_uuid",
    },
    model_funct=get_request,
)
def delete_request_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


def _lookup_and_merge_results(
    logger: logging.Logger,
    vector_results: List[Dict[str, Any]],
    merge_rule: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Perform a lookup in the graph database for each vector result and merge the results based on the specified merge rule.

    Args:
        vector_results (List[Dict[str, Any]]): The results from the vector search.
        merge_rule (Dict[str, Any]): The rules defining how to merge vector and graph data.
        logger (Any): The logger instance for logging information and errors.

    Returns:
        List[Dict[str, Any]]: The merged results, combining vector and graph data.
    """
    try:
        merge_key = merge_rule["merge_key"]
        graph_attributes = merge_rule["attributes_to_include"]["graph"]

        # Extract transaction IDs from vector results for lookup
        transaction_ids = [
            f"'{vector_item.get(merge_key)}'"
            for vector_item in vector_results
            if vector_item.get(merge_key)
        ]

        if not transaction_ids:
            return []

        # Construct the Cypher query for bulk graph lookup
        cypher_query = (
            f"MATCH (n)-[r]->(m) WHERE n.{merge_key} IN [{', '.join(transaction_ids)}] "
            f"RETURN {', '.join([f'n.{attr} AS {attr}' for attr in graph_attributes] + ['type(r) AS relationship_type', 'm.name AS related_entity'])}"
        )
        logger.info(f"Generated Cypher query for bulk lookup: {cypher_query}")

        # Execute the Cypher query
        _, graph_results = neo4j_connector.execute_cypher_query_with_pagination(
            cypher_query,
            database=neo4j_database,
            limit=len(transaction_ids),
            skip=0,
            get_total=False,
        )

        # Organize graph results into a lookup dictionary
        graph_lookup = {}
        for result in graph_results:
            key = result[merge_key]
            if key not in graph_lookup:
                graph_lookup[key] = {
                    attr: result.get(attr) for attr in graph_attributes
                }
                graph_lookup[key]["relationships"] = []
            graph_lookup[key]["relationships"].append(
                {
                    "type": result.get("relationship_type"),
                    "related_entity": result.get("related_entity"),
                }
            )

        # Merge vector results with corresponding graph data
        merged_results = []
        for vector_item in vector_results:
            merged_item = {merge_key: vector_item.get(merge_key)}

            # Add vector attributes to the merged result
            merged_item.update(
                {
                    attr: vector_item.get(attr)
                    for attr in merge_rule["attributes_to_include"]["vector"]
                    if attr in vector_item
                }
            )

            # Add graph attributes if available
            graph_data = graph_lookup.get(vector_item.get(merge_key), {})
            merged_item.update(graph_data)

            merged_results.append(merged_item)

        return merged_results

    except Exception as e:
        logger.error(f"Error during lookup and merge: {traceback.format_exc()}")
        raise e


def _is_similarity_search(user_query: str) -> bool:
    """Check if the user query indicates a similarity search."""
    response = openai_client.chat.completions.create(
        model=openai_model,
        messages=[
            {
                "role": "system",
                "content": system_contents["is_similarity_search"],
            },
            {
                "role": "user",
                "content": f"Is this query ({user_query}) a similarity search?",
            },
        ],
    )
    is_similarity_search = response.choices[0].message.content
    if is_similarity_search == "true":
        return True
    return False


# Use AI to generate Cypher query dynamically based on schema
def _generate_cypher_query(user_query: str, graph_schema: str) -> str:
    response = openai_client.chat.completions.create(
        model=openai_model,
        messages=[
            {
                "role": "system",
                "content": system_contents["generate_cypher_query"],
            },
            {
                "role": "user",
                "content": f"Generate a Cypher query for: {user_query} using schema: {graph_schema}",
            },
        ],
    )
    cypher_query = response.choices[0].message.content
    if cypher_query.startswith("Unable to retrieve the graph schema."):
        raise SchemaRetrievalError(cypher_query)
    if cypher_query.startswith("Could you provide more details?"):
        raise InsufficientDetailsError(cypher_query)

    return cypher_query


# Retrieve the knowledge graph metadata.
def _get_enabled_knowledge_graph_metadata(
    document_source: str,
) -> KnowledgeGraphMetadataModel:
    count = KnowledgeGraphMetadataModel.count(
        document_source,
        None,
        filter_condition=(KnowledgeGraphMetadataModel.status == True),
    )
    if count == 0:
        raise Exception("No knowledge graph metadata found")
    results = KnowledgeGraphMetadataModel.query(
        document_source,
        None,
        filter_condition=(KnowledgeGraphMetadataModel.status == True),
    )
    return results.next()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(
        lambda e: not isinstance(e, (SchemaRetrievalError, InsufficientDetailsError))
    ),
    reraise=True,
)
def _query_graph(
    logger: logging.Logger, cypher_query: str, offset: int, limit: int
) -> Tuple[int, List[Dict[str, Any]]]:
    """Executes a query on the graph database."""
    try:
        # Retrieve the total count and first batch of results
        return neo4j_connector.execute_cypher_query_with_pagination(
            cypher_query,
            database=neo4j_database,
            limit=limit,
            skip=offset,
            get_total=True,
        )
    except Exception as e:
        logger.error(f"Graph query failed: {traceback.format_exc()}")
        raise e


def _query_vector(
    logger: logging.Logger,
    user_query: str,
    index_name: str,
    hybrid_fields: str,
    k: int,
    offset: int,
    limit: int,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Executes a query on the vector search engine."""
    try:
        return redis_stack_connector.search_redis(
            user_query,
            index_name,
            vector_field=redis_index_config[index_name]["vector_field"],
            return_fields=redis_index_config[index_name]["return_fields"],
            hybrid_fields=hybrid_fields,
            k=k,
            offset=offset,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Vector query failed: {traceback.format_exc()}")
        raise e


# Define the updated function and helper methods
def _process_and_merge_results(
    logger: logging.Logger, **kwargs: Dict[str, Any]
) -> List[Dict[str, Any]]:
    try:
        # Extract parameters from kwargs
        user_query = kwargs.get("user_query")
        index_name = kwargs.get("index_name")
        document_source = kwargs.get("document_source")
        hybrid_fields = kwargs.get("hybrid_fields", "*")
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", 100)
        k = kwargs.get("k", redis_index_config[index_name]["k"])
        is_similarity_search = kwargs.get("is_similarity_search")
        cypher_query = kwargs.get("cypher_query", None)

        if is_similarity_search:
            vector_results_total, vector_results = _query_vector(
                logger, user_query, index_name, hybrid_fields, k, offset, limit
            )

            # Retrieve metadata and merge results
            knowledge_graph_metadata = _get_enabled_knowledge_graph_metadata(
                document_source
            )
            merged_results = _lookup_and_merge_results(
                logger,
                Utility.json_loads(Utility.json_dumps(vector_results)),
                knowledge_graph_metadata.merge_rule,
            )

            return vector_results_total, merged_results

        # Query functions
        graph_results_total, graph_results = _query_graph(
            logger, cypher_query, offset, limit
        )

        return graph_results_total, graph_results

    except Exception as e:
        logger.error(f"Error processing and merging results: {traceback.format_exc()}")
        raise e


def request_decorator() -> Callable:
    def actual_decorator(original_function: Callable) -> Callable:
        @functools.wraps(original_function)
        def wrapper_function(*args: List, **kwargs: Dict[str, any]) -> Any:
            try:
                cols = {
                    "document_source": kwargs["document_source"],
                    "user_query": kwargs["user_query"],
                    "updated_by": "system",
                }
                request = insert_update_request_handler(args[0], **cols)

                is_similarity_search = _is_similarity_search(kwargs["user_query"])
                kwargs["is_similarity_search"] = is_similarity_search
                cols.update({"is_similarity_search": is_similarity_search})

                if not is_similarity_search:
                    cypher_query = _generate_cypher_query(
                        kwargs["user_query"], graph_schema
                    )
                    args[0].context.get("logger").info(
                        f"Generated Cypher query: {cypher_query}"
                    )
                    cols.update({"cypher_query": cypher_query})
                    kwargs["cypher_query"] = cypher_query

                request = insert_update_request_handler(args[0], **cols)

                result = original_function(*args, **kwargs)

                cols.update(
                    {
                        "request_uuid": request.request_uuid,
                        "results": result.results,
                    }
                )
                request = insert_update_request_handler(args[0], **cols)

                return result
            except Exception as e:
                log = traceback.format_exc()
                cols.update(
                    {
                        "request_uuid": request.request_uuid,
                        "request_note": log,
                    }
                )
                request = insert_update_request_handler(args[0], **cols)
                args[0].context.get("logger").error(log)
                raise e

        return wrapper_function

    return actual_decorator


@request_decorator()
def resolve_knowledge_rag_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeRagType:
    total, results = _process_and_merge_results(info.context.get("logger"), **kwargs)
    return KnowledgeRagType(results=results, total=total)


def module_exists(logger: logging.Logger, module_name: str) -> bool:
    """Check if the module exists in the specified path."""
    module_dir = os.path.join(adaptor_extract_path, module_name)
    if os.path.exists(module_dir) and os.path.isdir(module_dir):
        logger.info(f"Module {module_name} found in {adaptor_extract_path}.")
        return True
    logger.info(f"Module {module_name} not found in {adaptor_extract_path}.")
    return False


def download_and_extract_module(logger: logging.Logger, module_name: str) -> None:
    """Download and extract the module from S3 if not already extracted."""
    key = f"{module_name}.zip"
    zip_path = f"{adaptor_zip_path}/{key}"

    logger.info(f"Downloading module from S3: bucket={adaptor_bucket_name}, key={key}")
    aws_s3.download_file(adaptor_bucket_name, key, zip_path)
    logger.info(f"Downloaded {key} from S3 to {zip_path}")

    # Extract the ZIP file
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(adaptor_extract_path)
    logger.info(f"Extracted module to {adaptor_extract_path}")


def get_data_adaptor_function(
    logger: logging.Logger,
    data_source_type: str,
    data_source_name: str,
    function_name: str,
) -> Optional[Callable]:
    try:
        data_source = get_data_source(data_source_type, data_source_name)

        if not module_exists(logger, data_source.module_name):
            # Download and extract the module if it doesn't exist
            download_and_extract_module(logger, data_source.module_name)

        # Add the extracted module to sys.path
        module_path = f"{adaptor_extract_path}/{data_source.module_name}"
        if module_path not in sys.path:
            sys.path.append(module_path)

        data_source_class = getattr(
            __import__(data_source.module_name), data_source.class_name
        )

        configuration = (
            data_source.configuration.__dict__["attribute_values"]
            if data_source.__dict__["attribute_values"].get("configuration")
            else {}
        )

        setting = dict(configuration, **{"data_views": data_source.data_views})

        return getattr(
            data_source_class(
                logger,
                **Utility.json_loads(Utility.json_dumps(setting)),
            ),
            function_name,
        )
    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


def resolve_data_view_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DataViewType:
    data_source_type = kwargs.get("data_source_type")
    data_source_name = kwargs.get("data_source_name")
    data_view_name = kwargs.get("data_view_name")
    parameters = kwargs.get("parameters", {})

    try:
        data_view_function = get_data_adaptor_function(
            info.context.get("logger"),
            data_source_type,
            data_source_name,
            "get_data_view",
        )
        data_view = data_view_function(data_view_name, **parameters)

        return DataViewType(**data_view)
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").error(log)
        raise e
