#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from time import perf_counter
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
from ..types.long_term_memory import LongTermMemoryType, LongTermMemoryListType


class LongTermMemoryModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-long_term_memories"

    user_uuid = UnicodeAttribute(hash_key=True)
    ltm_version_id = UnicodeAttribute(range_key=True)
    profile = MapAttribute(null=True)
    interests = ListAttribute(of=MapAttribute, null=True)
    preferences = ListAttribute(of=MapAttribute, null=True)
    needs = ListAttribute(of=MapAttribute, null=True)
    last_stm_time = UTCDateTimeAttribute()
    create_log = MapAttribute(null=True)
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_long_term_memory(user_uuid: str, ltm_version_id: str) -> LongTermMemoryModel:
    result = LongTermMemoryModel.get(user_uuid, ltm_version_id)
    return result


def get_long_term_memory_count(user_uuid: str, ltm_version_id: str) -> int:
    return LongTermMemoryModel.count(
        user_uuid, LongTermMemoryModel.ltm_version_id == ltm_version_id
    )


def get_long_term_memory_type(info: ResolveInfo, ltm_history: LongTermMemoryModel) -> LongTermMemoryType:
    try:
        ltm_history_dict = ltm_history.__dict__["attribute_values"]
    except Exception:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise

    return LongTermMemoryType(**Utility.json_normalize(ltm_history_dict))


def resolve_long_term_memory(info: ResolveInfo, **kwargs: Dict[str, Any]) -> LongTermMemoryType:
    return get_long_term_memory_type(
        info,
        get_long_term_memory(kwargs.get("user_uuid"), kwargs.get("ltm_version_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["user_uuid", "ltm_version_id"],
    list_type_class=LongTermMemoryListType,
    type_funct=get_long_term_memory_type,
    scan_index_forward=False,
)
def resolve_long_term_memory_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    user_uuid = kwargs.get("user_uuid")
    ltm_version_ids = kwargs.get("ltm_version_ids")
    start_time = kwargs.get("start_time")
    end_time = kwargs.get("end_time")

    args = []
    inquiry_funct = LongTermMemoryModel.scan
    count_funct = LongTermMemoryModel.count
    if user_uuid:
        args = [user_uuid, None]
        inquiry_funct = LongTermMemoryModel.query

    print(f"args: {args}")

    the_filters = None  # We can add filters for the query.
    if start_time:
        the_filters &= UserHistoryMemoryModel.message_time >= pendulum.parse(start_time)
    if end_time:
        the_filters &= UserHistoryMemoryModel.message_time <= pendulum.parse(end_time)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "user_uuid",
        "range_key": "ltm_version_id",
    },
    range_key_required=True,
    model_funct=get_long_term_memory,
    count_funct=get_long_term_memory_count,
    type_funct=get_long_term_memory_type
)
def insert_update_long_term_memory(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    print(kwargs)
    user_uuid = kwargs.get("user_uuid")
    ltm_version_id = kwargs.get("ltm_version_id")
    if kwargs.get("entity") is None:
        cols = {
            "profile": kwargs["profile"],
            "interests": kwargs["interests"],
            "preferences": kwargs["preferences"],
            "needs": kwargs["needs"],
            "create_log": kwargs["create_log"],
            "last_stm_time": kwargs["last_stm_time"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        LongTermMemoryModel(
            user_uuid,
            ltm_version_id,
            **cols,
        ).save()
        return

    ltm_history = kwargs.get("entity")
    actions = [
        LongTermMemoryModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to LongTermMemoryModel attributes
    field_map = {
        "entities": LongTermMemoryModel.entities,
        "preferences": LongTermMemoryModel.preferences,
        "last_stm_time": LongTermMemoryModel.last_stm_time,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the ltm_history in the database
    ltm_history.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "user_uuid",
        "range_key": "ltm_version_id",
    },
    model_funct=get_long_term_memory,
)
def delete_long_term_memory(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
