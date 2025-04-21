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

from ..types.document import DocumentType, DocumentListType
from .utils import _get_data_source


class NumberMapAttribute(MapAttribute):
    value = NumberAttribute()


class DocumentExternalIdIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "document_external_id-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    document_source = UnicodeAttribute(hash_key=True)
    document_external_id = UnicodeAttribute(range_key=True)


class DocumentModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-documents"

    document_source = UnicodeAttribute(hash_key=True)
    document_uuid = UnicodeAttribute(range_key=True)
    document_external_id = UnicodeAttribute()
    chunk_index = NumberAttribute(default=0)
    endpoint_id = UnicodeAttribute()
    document_title = UnicodeAttribute()
    document_content = UnicodeAttribute()
    title_embedding = ListAttribute(of=NumberAttribute, null=True)
    content_embedding = ListAttribute(of=NumberAttribute, null=True)
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    document_external_id_index = DocumentExternalIdIndex()


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


def resolve_document(
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
def resolve_document_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
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
def insert_update_document(
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
def delete_document(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
