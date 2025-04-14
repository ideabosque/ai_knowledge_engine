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
from ..types.document_process_task import DocumentProcessTaskType, DocumentProcessTaskListType
from .utils import _get_data_source


class DocumentProcessTaskModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-document_process_tasks"

    document_source = UnicodeAttribute(hash_key=True)
    process_task_uuid = UnicodeAttribute(range_key=True)
    endpoint_id = UnicodeAttribute()
    process_status = UnicodeAttribute(default="initial")
    process_note = UnicodeAttribute(null=True)
    cut_time = UTCDateTimeAttribute(null=True)
    start_time = UTCDateTimeAttribute()
    end_time = UTCDateTimeAttribute(null=True)


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


def resolve_document_process_task(
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
def resolve_document_process_task_list(
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
def insert_update_document_process_task(
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
def delete_document_process_task(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> bool:
    kwargs.get("entity").delete()
    return True
