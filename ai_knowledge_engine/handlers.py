#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from tenacity import retry, stop_after_attempt, wait_exponential

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
    DocumentSourceModel,
    KnowledgeGraphMetadataModel,
)
from .types import (
    DataSourceListType,
    DataSourceType,
    DocumentListType,
    DocumentProcessEntityListType,
    DocumentProcessEntityType,
    DocumentProcessTaskListType,
    DocumentProcessTaskType,
    DocumentSourceListType,
    DocumentSourceType,
    DocumentType,
    KnowledgeGraphMetadataListType,
    KnowledgeGraphMetadataType,
)


def handlers_init(logger: logging.Logger, **setting: Dict[str, Any]) -> None:
    try:
        pass
    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


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
        document_source = _get_document_source(
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
        if kwargs.get("title_embedding") is not None:
            cols["title_embedding"] = kwargs["title_embedding"]
        if kwargs.get("content_embedding") is not None:
            cols["content_embedding"] = kwargs["content_embedding"]
        if kwargs.get("log") is not None:
            cols["log"] = kwargs["log"]
        if kwargs.get("status") is not None:
            cols["status"] = kwargs["status"]
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
        "log": DocumentModel.log,
        "status": DocumentModel.status,
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
def get_document_source(
    document_type: str, document_source: str
) -> DocumentSourceModel:
    return DocumentSourceModel.get(document_type, document_source)


def get_document_source_count(document_type: str, document_source: str) -> int:
    return DocumentSourceModel.count(
        document_type, DocumentSourceModel.document_source == document_source
    )


def _get_document_source(document_type: str, document_source: str) -> Dict[str, Any]:
    document_source = get_document_source(document_type, document_source)
    return {
        "document_type": document_source.document_type,
        "document_source": document_source.document_source,
        "module_name": document_source.module_name,
        "class_name": document_source.class_name,
        "configuration": document_source.configuration,
    }


def get_document_source_type(
    info: ResolveInfo, document_source: DocumentSourceModel
) -> DocumentSourceType:
    document_source = document_source.__dict__["attribute_values"]
    return DocumentSourceType(**Utility.json_loads(Utility.json_dumps(document_source)))


def resolve_document_source_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentSourceType:
    return get_document_source_type(
        info,
        get_document_source(kwargs.get("document_type"), kwargs.get("document_source")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["document_type", "document_source"],
    list_type_class=DocumentSourceListType,
    type_funct=get_document_source_type,
)
def resolve_document_source_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    document_type = kwargs.get("document_type")
    module_name = kwargs.get("module_name")
    class_name = kwargs.get("class_name")

    args = []
    inquiry_funct = DocumentSourceModel.scan
    count_funct = DocumentSourceModel.count
    if document_type:
        args = [document_type, None]
        inquiry_funct = DocumentSourceModel.query

    the_filters = None  # We can add filters for the query.
    if module_name:
        the_filters &= DocumentSourceModel.module_name.contains(module_name)
    if class_name:
        the_filters &= DocumentSourceModel.class_name.contains(class_name)

    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "document_type",
        "range_key": "document_source",
    },
    range_key_required=True,
    model_funct=get_document_source,
    count_funct=get_document_source_count,
    type_funct=get_document_source_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_document_source_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentSourceType:
    document_type = kwargs.get("document_type")
    document_source = kwargs.get("document_source")
    if kwargs.get("entity") is None:
        DocumentSourceModel(
            document_type,
            document_source,
            module_name=kwargs["module_name"],
            class_name=kwargs["class_name"],
            configuration=kwargs["configuration"],
            updated_by=kwargs["updated_by"],
            created_at=pendulum.now("UTC"),
            updated_at=pendulum.now("UTC"),
        ).save()
        return

    document_source = kwargs.get("entity")
    actions = [
        DocumentSourceModel.updated_by.set(kwargs["updated_by"]),
        DocumentSourceModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to DocumentSourceModel attributes
    field_map = {
        "module_name": DocumentSourceModel.module_name,
        "class_name": DocumentSourceModel.class_name,
        "configuration": DocumentSourceModel.configuration,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the session
    DocumentSourceModel.update(actions=actions)

    return


@delete_decorator(
    keys={
        "hash_key": "document_type",
        "range_key": "document_source",
    },
    model_funct=get_document_source,
)
def delete_document_source_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
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
        "document_source": _get_document_source(
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
        document_source = _get_document_source(
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
        if kwargs.get("log") is not None:
            cols["log"] = kwargs["log"]
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
        "log": DocumentProcessEntityModel.log,
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
        document_source = _get_document_source(
            knowledge_graph_metadata.document_type,
            knowledge_graph_metadata.document_source,
        )
        data_source = _get_data_source(
            knowledge_graph_metadata.data_source_type,
            knowledge_graph_metadata.data_source_name,
        )
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    knowledge_graph_metadata = knowledge_graph_metadata.__dict__["attribute_values"]
    knowledge_graph_metadata["document_source"] = document_source
    knowledge_graph_metadata["data_source"] = data_source
    knowledge_graph_metadata.pop("document_type")
    knowledge_graph_metadata.pop("data_source_type")
    knowledge_graph_metadata.pop("data_source_name")
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
    data_source_name = kwargs.get("data_source_name")
    data_source_types = kwargs.get("data_source_types")
    data_view_name = kwargs.get("data_view_name")
    status = kwargs.get("status")
    args = []
    inquiry_funct = KnowledgeGraphMetadataModel.scan
    count_funct = KnowledgeGraphMetadataModel.count
    if document_source:
        args = [document_type, None]
        inquiry_funct = KnowledgeGraphMetadataModel.query

    the_filters = None  # We can add filters for the query.
    if document_types:
        the_filters &= KnowledgeGraphMetadataModel.document_type.is_in(*document_types)
    if data_source_name:
        the_filters &= KnowledgeGraphMetadataModel.data_source_name.contains(
            data_source_name
        )
    if data_source_types:
        the_filters &= KnowledgeGraphMetadataModel.data_source_type.is_in(
            *data_source_types
        )
    if data_view_name:
        the_filters &= KnowledgeGraphMetadataModel.data_view_name.contains(
            data_view_name
        )
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
            "data_source_name": kwargs["data_source_name"],
            "data_source_type": kwargs["data_source_type"],
            "data_view_name": kwargs["data_view_name"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if kwargs.get("structured_fields") is not None:
            cols["structured_fields"] = kwargs["structured_fields"]
        if kwargs.get("unstructured_attributes") is not None:
            cols["unstructured_attributes"] = kwargs["unstructured_attributes"]
        if kwargs.get("linkage_rules") is not None:
            cols["linkage_rules"] = kwargs["linkage_rules"]
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
        "document_type": KnowledgeGraphMetadataModel.document_type,
        "data_source_name": KnowledgeGraphMetadataModel.data_source_name,
        "data_source_type": KnowledgeGraphMetadataModel.data_source_type,
        "data_view_name": KnowledgeGraphMetadataModel.data_view_name,
        "structured_fields": KnowledgeGraphMetadataModel.structured_fields,
        "unstructured_attributes": KnowledgeGraphMetadataModel.unstructured_attributes,
        "linkage_rules": KnowledgeGraphMetadataModel.linkage_rules,
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
