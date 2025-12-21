#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function
from tracemalloc import start

__author__ = "bibow"

from time import perf_counter
import traceback
from enum import Enum
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
from ..types.short_term_memory import ShortTermMemoryType, ShortTermMemoryListType


class MessageTimeIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "message_time-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    user_uuid = UnicodeAttribute(hash_key=True)
    message_time = UnicodeAttribute(range_key=True)


class ShortTermMemoryModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-short_term_memories"

    user_uuid = UnicodeAttribute(hash_key=True)
    memory_uuid = UnicodeAttribute(range_key=True)
    thread_uuid = UnicodeAttribute()
    message_uuid = UnicodeAttribute()
    profile = MapAttribute(null=True)
    entities = ListAttribute(of=MapAttribute, null=True)
    preferences = ListAttribute(of=MapAttribute, null=True)
    interests = ListAttribute(of=MapAttribute, null=True)
    needs = ListAttribute(of=MapAttribute, null=True)
    message_time = UTCDateTimeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    confidence = NumberAttribute()
    status = UnicodeAttribute()
    ltm_version_id = UnicodeAttribute()
    message_time_index = MessageTimeIndex()


class MemoryStatusEnums(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_short_term_memory(user_uuid: str, memory_uuid: str) -> ShortTermMemoryModel:
    result = ShortTermMemoryModel.get(user_uuid, memory_uuid)
    return result


def get_short_term_memory_count(user_uuid: str, memory_uuid: str) -> int:
    return ShortTermMemoryModel.count(
        user_uuid, ShortTermMemoryModel.memory_uuid == memory_uuid
    )


def get_short_term_memory_type(info: ResolveInfo, memory: ShortTermMemoryModel) -> ShortTermMemoryType:
    try:
        memory_dict = memory.__dict__["attribute_values"]
    except Exception:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise

    return ShortTermMemoryType(**Utility.json_normalize(memory_dict))


def resolve_short_term_memory(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ShortTermMemoryType:
    return get_short_term_memory_type(
        info,
        get_short_term_memory(kwargs.get("user_uuid"), kwargs.get("memory_uuid")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["user_uuid", "memory_uuid", "message_time"],
    list_type_class=ShortTermMemoryListType,
    type_funct=get_short_term_memory_type,
    scan_index_forward=True,
)
def resolve_short_term_memory_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    user_uuid = kwargs.get("user_uuid")
    ltm_version_id = kwargs.get("ltm_version_id")
    message_uuids = kwargs.get("message_uuids", [])
    message_time_gt = kwargs.get("message_time_gt")
    message_time_lt = kwargs.get("message_time_lt")
    status = kwargs.get("status")

    args = []
    inquiry_funct = ShortTermMemoryModel.scan
    count_funct = ShortTermMemoryModel.count
    if user_uuid:
        range_key_condition = None
        if message_time_gt is not None and message_time_lt is not None:
            range_key_condition = ShortTermMemoryModel.message_time.between(
                message_time_gt, message_time_lt
            )
        elif message_time_gt is not None:
            range_key_condition = ShortTermMemoryModel.message_time > message_time_gt
        elif message_time_lt is not None:
            range_key_condition = ShortTermMemoryModel.message_time < message_time_lt
        
        args = [user_uuid, range_key_condition]
        inquiry_funct = ShortTermMemoryModel.message_time_index.query
        count_funct = ShortTermMemoryModel.message_time_index.count

    print(f"args: {args}")

    the_filters = None  # We can add filters for the query.
    if message_uuids:
        the_filters &= ShortTermMemoryModel.message_uuid.is_in(*message_uuids)
    if "ltm_version_id" in kwargs:
        the_filters &= ShortTermMemoryModel.ltm_version_id == ltm_version_id
    # elif "ltm_version_id" in kwargs:
        # the_filters &= ShortTermMemoryModel.ltm_version_id.does_not_exist()
    if status:
        the_filters &= ShortTermMemoryModel.status == status

    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "user_uuid",
        "range_key": "memory_uuid",
    },
    range_key_required=True,
    model_funct=get_short_term_memory,
    count_funct=get_short_term_memory_count,
    type_funct=get_short_term_memory_type
)
def insert_update_short_term_memory(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    user_uuid = kwargs.get("user_uuid")
    memory_uuid = kwargs.get("memory_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "thread_uuid": kwargs["thread_uuid"],
            "message_time": kwargs["message_time"],
            "profile": kwargs.get("profile", {}),
            "entities": kwargs["entities"],
            "interests": kwargs["interests"],
            "preferences": kwargs["preferences"],
            "needs": kwargs.get("needs", []),
            "message_uuid": kwargs["message_uuid"],
            "confidence": kwargs.get("confidence", 0.5),
            "status": kwargs.get("status", MemoryStatusEnums.ACTIVE.value),
            "ltm_version_id": kwargs.get("ltm_version_id", ""),
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        ShortTermMemoryModel(
            user_uuid,
            memory_uuid,
            **cols,
        ).save()
        return

    memory = kwargs.get("entity")
    actions = [
        ShortTermMemoryModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to ShortTermMemoryModel attributes
    field_map = {
        "thread_uuid": ShortTermMemoryModel.thread_uuid,
        "message_time": ShortTermMemoryModel.message_time,
        "profile": ShortTermMemoryModel.profile,
        "entities": ShortTermMemoryModel.entities,
        "interests": ShortTermMemoryModel.interests,
        "preferences": ShortTermMemoryModel.preferences,
        "needs": ShortTermMemoryModel.needs,
        "message_uuid": ShortTermMemoryModel.message_uuid,
        "confidence": ShortTermMemoryModel.confidence,
        "status": ShortTermMemoryModel.status,
        "ltm_version_id": ShortTermMemoryModel.ltm_version_id,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the memory in the database
    memory.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "user_uuid",
        "range_key": "memory_uuid",
    },
    model_funct=get_short_term_memory,
)
def delete_short_term_memory(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
