#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import json
import logging
import os
import re
import sys
import traceback
import uuid
import zipfile
from typing import Any, Callable, Dict, List, Optional, Tuple

import boto3
import pendulum
import tiktoken
from graphene import ResolveInfo
from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from silvaengine_dynamodb_base import (
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility

from ..models import (
    DataSourceModel,
    DocumentModel,
    DocumentProcessEntityModel,
    DocumentProcessTaskModel,
    KnowledgeGraphMetadataModel,
    RequestModel,
)
from ..types import (
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
graph_db_connector = None
vector_db_connector = None
redis_index_config = None
graph_schema = None
system_contents = None
module_bucket_name = None
module_zip_path = None
module_extract_path = None
aws_s3 = None
aws_s3_bucket = None
embedding_model = None


def handlers_init(logger: logging.Logger, **setting: Dict[str, Any]) -> None:
    try:
        global embedding_model, openai_model, system_contents
        global module_bucket_name, module_zip_path, module_extract_path
        global aws_s3, aws_s3_bucket
        global openai_client
        global graph_db_connector, graph_schema
        global vector_db_connector, redis_index_config

        _setup_parameters(setting)
        _setup_function_paths(setting)
        _initialize_aws_services(setting)
        _initialize_openai_client(setting)
        _initialize_graph_database(logger, setting)
        _initialize_vector_database(logger, setting)

    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


def _setup_parameters(setting: Dict[str, Any]) -> None:
    global embedding_model, openai_model, system_contents

    if "EMBEDDING_MODEL" in setting:
        embedding_model = setting["EMBEDDING_MODEL"]
    if "openai_model" in setting:
        openai_model = setting["openai_model"]
    if "system_contents" in setting:
        system_contents = setting["system_contents"]


def _initialize_aws_services(setting: Dict[str, Any]) -> None:
    global aws_s3, aws_s3_bucket

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

    aws_s3_bucket = setting.get("swap_bucket_name")
    aws_s3 = boto3.client("s3", **aws_credentials)


def _initialize_openai_client(setting: Dict[str, Any]) -> None:
    global openai_client

    if "openai_api_key" in setting:
        openai_setting = {"api_key": setting["openai_api_key"]}

        if "openai_base_url" in setting:
            openai_setting.update({"base_url": setting["openai_base_url"]})

        openai_client = OpenAI(**openai_setting)


def _initialize_graph_database(logger: logging.Logger, setting: Dict[str, Any]) -> None:
    global graph_db_connector, graph_schema
    if "graph_db_connector_config" in setting:
        graph_db_connector = _get_class_object(
            logger,
            setting["graph_db_connector_config"]["module_name"],
            setting["graph_db_connector_config"]["class_name"],
            **setting["graph_db_connector_config"]["setting"],
        )
        graph_schema = graph_db_connector.get_graph_schema()


def _initialize_vector_database(
    logger: logging.Logger, setting: Dict[str, Any]
) -> None:
    global vector_db_connector, redis_index_config
    if "vector_db_connector_config" in setting:
        vector_db_connector = _get_class_object(
            logger,
            setting["vector_db_connector_config"]["module_name"],
            setting["vector_db_connector_config"]["class_name"],
            **dict(
                setting["vector_db_connector_config"]["setting"],
                **{
                    "openai_api_key": setting["openai_api_key"],
                    "EMBEDDING_MODEL": embedding_model,
                },
            ),
        )


def _setup_function_paths(setting: Dict[str, Any]) -> None:
    global module_bucket_name, module_zip_path, module_extract_path
    module_bucket_name = setting.get("module_bucket_name")
    module_zip_path = setting.get("module_zip_path", "/tmp/adaptor_zips")
    module_extract_path = setting.get("module_extract_path", "/tmp/adaptors")
    os.makedirs(module_zip_path, exist_ok=True)
    os.makedirs(module_extract_path, exist_ok=True)


def _module_exists(logger: logging.Logger, module_name: str) -> bool:
    """Check if the module exists in the specified path."""
    module_dir = os.path.join(module_extract_path, module_name)
    if os.path.exists(module_dir) and os.path.isdir(module_dir):
        logger.info(f"Module {module_name} found in {module_extract_path}.")
        return True
    logger.info(f"Module {module_name} not found in {module_extract_path}.")
    return False


def _download_and_extract_module(logger: logging.Logger, module_name: str) -> None:
    """Download and extract the module from S3 if not already extracted."""
    key = f"{module_name}.zip"
    zip_path = f"{module_zip_path}/{key}"

    logger.info(f"Downloading module from S3: bucket={module_bucket_name}, key={key}")
    aws_s3.download_file(module_bucket_name, key, zip_path)
    logger.info(f"Downloaded {key} from S3 to {zip_path}")

    # Extract the ZIP file
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(module_extract_path)
    logger.info(f"Extracted module to {module_extract_path}")


def _get_class_object(
    logger: logging.Logger, module_name: str, class_name: str, **setting: Dict[str, Any]
) -> Optional[Callable]:
    try:
        if not _module_exists(logger, module_name):
            # Download and extract the module if it doesn't exist
            _download_and_extract_module(logger, module_name)

        # Add the extracted module to sys.path
        module_path = f"{module_extract_path}/{module_name}"
        if module_path not in sys.path:
            sys.path.append(module_path)

        _class = getattr(__import__(module_name), class_name)

        return _class(
            logger,
            **Utility.json_loads(Utility.json_dumps(setting)),
        )
    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


def _get_embedding(text: str) -> List[Dict[str, Any]]:
    text = text.replace("\n", " ")
    res = openai_client.embeddings.create(input=[text], model=embedding_model)
    return res.data[0].embedding


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
            document.endpoint_id, document.document_source
        )
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    document = document.__dict__["attribute_values"]
    document["document_source"] = document_source
    document.pop("endpoint_id")
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
    endpoint_id = info.context["endpoint_id"]
    document_title = kwargs.get("document_title")
    document_content = kwargs.get("document_content")

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
    if endpoint_id:
        the_filters &= DocumentModel.endpoint_id == endpoint_id
    if document_title:
        the_filters &= DocumentModel.document_title.contains(document_title)
    if document_content:
        the_filters &= DocumentModel.document_content.contains(document_content)

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
            "endpoint_id": info.context["endpoint_id"],
            "document_title": kwargs["document_title"],
            "document_content": kwargs["document_content"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in ["chunk_index", "title_embedding", "content_embedding"]:
            if key in kwargs:
                cols[key] = kwargs[key]
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
            document_process_task.endpoint_id, document_source
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
            document_process_task.endpoint_id,
            document_process_task.document_source,
        )
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    document_process_task = document_process_task.__dict__["attribute_values"]
    document_process_task["document_source"] = document_source
    document_process_task.pop("endpoint_id")
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
    attributes_to_get=["document_source", "process_task_uuid"],
    list_type_class=DocumentProcessTaskListType,
    type_funct=get_document_process_task_type,
)
def resolve_document_process_task_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    document_source = kwargs.get("document_source")
    endpoint_id = info.context["endpoint_id"]
    process_statuses = kwargs.get("process_statuses")
    args = []
    inquiry_funct = DocumentProcessTaskModel.scan
    count_funct = DocumentProcessTaskModel.count
    if document_source:
        args = [document_source, None]
        inquiry_funct = DocumentProcessTaskModel.query

    the_filters = None  # We can add filters for the query.
    if endpoint_id:
        the_filters &= DocumentProcessTaskModel.endpoint_id == endpoint_id
    if process_statuses:
        the_filters &= DocumentProcessTaskModel.process_status.is_in(*process_statuses)

    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "document_source",
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
            "endpoint_id": info.context["endpoint_id"],
            "start_time": pendulum.now("UTC"),
        }
        if "process_status" in kwargs:
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
        "hash_key": "document_source",
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
        for key in [
            "logs",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]

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


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_enabled_knowledge_graph_metadata(
    document_source: str,
) -> KnowledgeGraphMetadataModel:
    try:
        results = KnowledgeGraphMetadataModel.query(
            document_source,
            None,
            filter_condition=(KnowledgeGraphMetadataModel.status == True),
            scan_index_forward=False,
            limit=1,
        )
        knowledge_graph_metadata = results.next()

        return knowledge_graph_metadata
    except StopIteration:
        return None


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
            knowledge_graph_metadata.endpoint_id,
            knowledge_graph_metadata.document_source,
        )
        structured_data_views = [
            {
                "data_source": _get_data_source(
                    structured_data_view["endpoint_id"],
                    structured_data_view["data_source_name"],
                ),
                "data_view_name": structured_data_view.get("data_view_name"),
                "adaptor_filter_attribute": structured_data_view.get(
                    "adaptor_filter_attribute"
                ),
                "graph_node_label": structured_data_view.get("graph_node_label"),
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
    knowledge_graph_metadata.pop("endpoint_id")
    return KnowledgeGraphMetadataType(
        **Utility.json_loads(Utility.json_dumps(knowledge_graph_metadata))
    )


def resolve_knowledge_graph_metadata_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeGraphMetadataType:
    if "metadata_version_uuid" in kwargs:
        return get_knowledge_graph_metadata_type(
            info,
            get_knowledge_graph_metadata(
                kwargs.get("document_source"), kwargs.get("metadata_version_uuid")
            ),
        )

    return get_knowledge_graph_metadata_type(
        info,
        _get_enabled_knowledge_graph_metadata(kwargs.get("document_source")),
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
    endpoint_id = info.context["endpoint_id"]
    status = kwargs.get("status")
    args = []
    inquiry_funct = KnowledgeGraphMetadataModel.scan
    count_funct = KnowledgeGraphMetadataModel.count
    if document_source:
        args = [document_source, None]
        inquiry_funct = KnowledgeGraphMetadataModel.query

    the_filters = None  # We can add filters for the query.
    if endpoint_id:
        the_filters &= KnowledgeGraphMetadataModel.endpoint_id == endpoint_id
    if status:
        the_filters &= KnowledgeGraphMetadataModel.status == status
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


def _disable_knowledge_graph_metadatas(info: ResolveInfo, document_source: str) -> None:
    try:
        knowledge_graph_metadatas = KnowledgeGraphMetadataModel.query(
            document_source,
            None,
            filter_condition=KnowledgeGraphMetadataModel.status == True,
        )
        for knowledge_graph_metadata in knowledge_graph_metadatas:
            knowledge_graph_metadata.status = False
            knowledge_graph_metadata.save()
        return
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").error(log)
        raise e


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
            "endpoint_id": info.context["endpoint_id"],
            "status": True,
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }

        enabled_knowledge_graph_metadata = _get_enabled_knowledge_graph_metadata(
            document_source
        )
        if enabled_knowledge_graph_metadata:
            cols.update(
                {
                    k: v
                    for k, v in enabled_knowledge_graph_metadata.__dict__[
                        "attribute_values"
                    ].items()
                    if k
                    not in [
                        "endpoint_id",
                        "status",
                        "updated_by",
                        "created_at",
                        "updated_at",
                    ]
                }
            )
            _disable_knowledge_graph_metadatas(info, document_source)

        for key in [
            "structured_data_views",
            "structured_fields",
            "unstructured_attributes",
            "linkage_rules",
            "merge_rule",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]

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

    if "status" in kwargs and (
        kwargs["status"] == True and knowledge_graph_metadata.status == False
    ):
        _disable_knowledge_graph_metadatas(info, document_source)

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
        "hash_key": "document_source",
        "range_key": "metadata_version_uuid",
    },
    model_funct=get_knowledge_graph_metadata,
)
def delete_knowledge_graph_metadata_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> bool:
    if kwargs["entity"].status:
        results = KnowledgeGraphMetadataModel.query(
            kwargs["document_source"],
            None,
            filter_condition=KnowledgeGraphMetadataModel.status == False,
        )
        knowledge_graph_metadatas = [result for result in results]
        if len(knowledge_graph_metadatas) > 0:
            knowledge_graph_metadatas = sorted(
                knowledge_graph_metadatas, key=lambda x: x.updated_at, reverse=True
            )
            last_updated_record = knowledge_graph_metadatas[0]
            last_updated_record.status = True
            last_updated_record.save()

    kwargs["entity"].delete()

    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_data_source(endpoint_id: str, data_source_name: str) -> DataSourceModel:
    return DataSourceModel.get(endpoint_id, data_source_name)


def get_data_source_count(endpoint_id: str, data_source_name: str) -> int:
    return DataSourceModel.count(
        endpoint_id, DataSourceModel.data_source_name == data_source_name
    )


def _get_data_source(endpoint_id: str, data_source_name: str) -> DataSourceModel:
    data_source = get_data_source(endpoint_id, data_source_name)
    return {
        "endpoint_id": endpoint_id,
        "data_source_name": data_source_name,
        "data_source_type": data_source.data_source_type,
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
        get_data_source(info.context["endpoint_id"], kwargs.get("data_source_name")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["data_source_type", "data_source_name", "data_source_type"],
    list_type_class=DataSourceListType,
    type_funct=get_data_source_type,
)
def resolve_data_source_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    endpoint_id = info.context["endpoint_id"]
    data_source_type = kwargs.get("data_source_type")
    module_name = kwargs.get("module_name")
    class_name = kwargs.get("class_name")
    args = []
    inquiry_funct = DataSourceModel.scan
    count_funct = DataSourceModel.count
    if endpoint_id:
        args = [endpoint_id, None]
        inquiry_funct = DataSourceModel.query
        if data_source_type:
            inquiry_funct = DataSourceModel.data_source_type_index.query
            args[1] = DataSourceModel.data_source_type == data_source_type
            count_funct = DataSourceModel.data_source_type_index.count

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
        "hash_key": "endpoint_id",
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
    endpoint_id = kwargs.get("endpoint_id")
    data_source_name = kwargs.get("data_source_name")
    if kwargs.get("entity") is None:
        cols = {
            "data_source_type": kwargs["data_source_type"],
            "module_name": kwargs["module_name"],
            "class_name": kwargs["class_name"],
            "configuration": kwargs["configuration"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if "data_views" in kwargs:
            cols["data_views"] = kwargs["data_views"]
        DataSourceModel(
            endpoint_id,
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
        "data_source_type": DataSourceModel.data_source_type,
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
        "hash_key": "endpoint_id",
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
        for key in ["cypher_query", "is_similarity_search", "results", "request_note"]:
            if key in kwargs:
                cols[key] = kwargs[key]
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
        vector_merge_key = merge_rule["vector_merge_key"]
        graph_merge_node = merge_rule["graph_merge_node"]
        graph_merge_key = merge_rule["graph_merge_key"]
        vector_attributes = merge_rule["vector_attributes_to_include"]

        # Extract transaction IDs from vector results for lookup
        transaction_ids = [
            f"{vector_item.get(vector_merge_key)}"
            for vector_item in vector_results
            if vector_item.get(vector_merge_key)
        ]

        if not transaction_ids:
            return []

        cypher_query = _generate_cypher_query(
            f"""Retrieve the node ({graph_merge_node}) associated with `{graph_merge_key}` within the specified `{transaction_ids}`. Return the node as `node`.""",
            graph_schema,
        )

        logger.info(f"Generated Cypher query for bulk lookup: {cypher_query}")

        # Execute the Cypher query
        _, graph_results = graph_db_connector.execute_cypher_query_with_pagination(
            cypher_query,
            limit=len(transaction_ids),
            skip=0,
            get_total=False,
        )

        # Organize graph results into a lookup dictionary
        graph_lookup = {}
        for result in graph_results:
            key = result["node"].get(
                graph_merge_key
            )  # Adjust based on how the node key is identified
            if key not in graph_lookup:
                # Include all attributes from the node
                graph_lookup[key] = {
                    **result["node"],  # Unpack all attributes of the node
                }

        # Merge vector results with corresponding graph data
        merged_results = []
        for vector_item in vector_results:
            merged_item = {vector_merge_key: vector_item.get(vector_merge_key)}

            # Add vector attributes to the merged result
            merged_item.update(
                {
                    attr: vector_item.get(attr)
                    for attr in vector_attributes
                    if attr in vector_item
                }
            )

            # Add graph attributes if available
            graph_data = graph_lookup.get(vector_item.get(vector_merge_key), {})
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
                "content": f"Is this query ({user_query}) a similarity search based on schema: ({graph_schema})?",
            },
        ],
    )
    is_similarity_search = response.choices[0].message.content

    if is_similarity_search.startswith(
        "The query is ambiguous and does not provide enough information to determine if it pertains to a similarity search. Please provide additional context or clarify your intent."
    ):
        raise InsufficientDetailsError(is_similarity_search)

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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(
        lambda e: not isinstance(e, (SchemaRetrievalError, InsufficientDetailsError))
    ),
    reraise=True,
)
def _query_graph(
    logger: logging.Logger,
    document_source: str,
    request_uuid: str,
    cypher_query: str,
    offset: int,
    limit: int,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Executes a query on the graph database."""
    try:
        # Retrieve the total count and first batch of results
        request = RequestModel.get(document_source, request_uuid)
        request.cypher_query = cypher_query
        request.save()

        return graph_db_connector.execute_cypher_query_with_pagination(
            cypher_query,
            limit=limit,
            skip=offset,
            get_total=True,
        )
    except Exception as e:
        logger.error(f"Graph query failed: {traceback.format_exc()}")
        raise e


def _query_vector(
    logger: logging.Logger, user_query: str, index_name: str, **kwargs: Dict[str, Any]
) -> Tuple[int, List[Dict[str, Any]]]:
    """Executes a query on the vector search engine."""
    try:
        query_vector = _get_embedding(user_query)
        return vector_db_connector.search_vector(query_vector, index_name, **kwargs)
    except Exception as e:
        logger.error(f"Vector query failed: {traceback.format_exc()}")
        raise e


# Define the updated function and helper methods
def _process_and_merge_results(
    logger: logging.Logger, **kwargs: Dict[str, Any]
) -> KnowledgeRagType:
    # Extract parameters from kwargs
    user_query = kwargs.get("user_query")
    document_source = kwargs.get("document_source")
    request_uuid = kwargs.get("request_uuid")
    is_similarity_search = kwargs.get("is_similarity_search")

    # Retrieve metadata and merge results
    knowledge_graph_metadata = _get_enabled_knowledge_graph_metadata(document_source)
    index_name = f"{knowledge_graph_metadata.endpoint_id}:{knowledge_graph_metadata.document_source}"
    logger.info(f"Index name: {index_name}")

    if is_similarity_search:
        _kwargs = {
            "vector_field": kwargs.get("vector_field"),
            "fields_to_return": kwargs.get("fields_to_return"),
            **{
                key: kwargs[key]
                for key in ["filter_conditions", "top_k", "result_offset", "limit"]
                if key in kwargs
            },
        }

        vector_results_total, vector_results = _query_vector(
            logger, user_query, index_name, **_kwargs
        )

        merged_results = _lookup_and_merge_results(
            logger,
            Utility.json_loads(Utility.json_dumps(vector_results)),
            knowledge_graph_metadata.merge_rule,
        )

        return KnowledgeRagType(results=merged_results, total=vector_results_total)

    # Retrieve the total count and first batch of results
    cypher_query = _generate_cypher_query(user_query, graph_schema)
    logger.info(f"Generated Cypher query: {cypher_query}")

    # Query functions
    graph_results_total, graph_results = _query_graph(
        logger,
        document_source,
        request_uuid,
        cypher_query,
        kwargs.get("offset", 0),
        kwargs.get("limit", 100),
    )

    return KnowledgeRagType(results=graph_results, total=graph_results_total)


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

                is_similarity_search = kwargs.get("is_similarity_search")
                if is_similarity_search is None:
                    is_similarity_search = _is_similarity_search(kwargs["user_query"])
                    kwargs["is_similarity_search"] = is_similarity_search
                cols.update({"is_similarity_search": is_similarity_search})

                kwargs["request_uuid"] = request.request_uuid

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
    return _process_and_merge_results(info.context.get("logger"), **kwargs)


def _get_data_adaptor_function(
    logger: logging.Logger,
    data_source_type: str,
    data_source_name: str,
    function_name: str,
) -> Optional[Callable]:
    try:
        data_source = get_data_source(data_source_type, data_source_name)

        configuration = (
            data_source.configuration.__dict__["attribute_values"]
            if data_source.__dict__["attribute_values"].get("configuration")
            else {}
        )

        setting = dict(configuration, **{"data_views": data_source.data_views})

        class_object = _get_class_object(
            logger, data_source.module_name, data_source.class_name, **setting
        )

        return getattr(
            class_object,
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
        data_view_function = _get_data_adaptor_function(
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
