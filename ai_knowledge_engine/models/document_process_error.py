#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict, List

from pynamodb.attributes import (
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
import pendulum
from tenacity import retry, stop_after_attempt, wait_exponential
from graphene import ResolveInfo
from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
)
from silvaengine_utility import Utility
from ..types.document_process_task import DocumentProcessTaskType, DocumentProcessTaskListType
from .utils import _get_data_source


class DocumentProcessErrorModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-document_process_errors"

    document_source = UnicodeAttribute(hash_key=True)
    process_error_uuid = UnicodeAttribute(range_key=True)
    document_external_id = UnicodeAttribute()
    chunk_index = NumberAttribute(default=0)
    endpoint_id = UnicodeAttribute()
    document_title = UnicodeAttribute()
    document_content = UnicodeAttribute()
    error_message = UnicodeAttribute()
    process_status = UnicodeAttribute(default=0)
    process_count = NumberAttribute(default=0)
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_document_process_error(
    document_source: str, process_error_uuid: str
) -> DocumentProcessErrorModel:
    return DocumentProcessErrorModel.get(document_source, process_error_uuid)


@insert_update_decorator(
    keys={
        "hash_key": "document_source",
        "range_key": "process_error_uuid",
    },
    model_funct=get_document_process_error,
)
def insert_update_document_process_task(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessTaskType:
    document_source = kwargs.get("document_source")
    process_error_uuid = kwargs.get("process_error_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "document_external_id": kwargs["document_external_id"],
            "endpoint_id": info.context["endpoint_id"],
            "document_title": kwargs["document_title"],
            "document_content": kwargs["document_content"],
            "chunk_index": kwargs["chunk_index"],
            "error_message": kwargs["error_message"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if "process_status" in kwargs:
            cols["process_status"] = kwargs["process_status"]
        DocumentProcessErrorModel(document_source, process_error_uuid, **cols).save()
        return

    document_process_task = kwargs.get("entity")
    actions = [
        DocumentProcessErrorModel.updated_by.set(kwargs["updated_by"]),
        DocumentProcessErrorModel.updated_at.set(pendulum.now("UTC")),
        DocumentProcessErrorModel.process_count.set(DocumentProcessErrorModel.process_count + 1),
    ]

    # Map of kwargs keys to document_process_task attributes
    field_map = {
        "process_status": DocumentProcessErrorModel.process_status,
        "error_message": DocumentProcessErrorModel.error_message,
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
        "range_key": "process_error_uuid",
    },
    model_funct=get_document_process_error,
)
def delete_document_process_error(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> bool:
    kwargs.get("entity").delete()
    return True
