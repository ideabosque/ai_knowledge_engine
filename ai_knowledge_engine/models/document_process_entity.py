#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict, List

from pynamodb.attributes import (
    BooleanAttribute,
    ListAttribute,
    MapAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
import pendulum
from pynamodb.indexes import AllProjection, LocalSecondaryIndex
from tenacity import retry, stop_after_attempt, wait_exponential
from graphene import ResolveInfo
from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator
)
from silvaengine_utility import Utility
from ..types.document_process_entity import DocumentProcessEntityType, DocumentProcessEntityListType
from .utils import _get_document_process_task


class DocumentProcessEntityDocumentExternalIdIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "document_external_id-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    process_task_uuid = UnicodeAttribute(hash_key=True)
    document_external_id = UnicodeAttribute(range_key=True)


class DocumentProcessEntityModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-document_process_entities"

    process_task_uuid = UnicodeAttribute(hash_key=True)
    document_entity_uuid = UnicodeAttribute(range_key=True)
    document_external_id = UnicodeAttribute()
    document_source = UnicodeAttribute()
    document_version = UnicodeAttribute()
    logs = ListAttribute(of=MapAttribute, null=True)
    status = UnicodeAttribute(default="initial")
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    document_external_id_index = DocumentProcessEntityDocumentExternalIdIndex()


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


def resolve_document_process_entity(
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
def resolve_document_process_entity_list(
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
def insert_update_document_process_entity(
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
def delete_document_process_entity(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> bool:
    kwargs.get("entity").delete()
    return True
