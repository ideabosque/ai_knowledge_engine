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
from ..types.data_source import DataSourceType, DataSourceListType


class DataSourceTypeIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "data_source_type-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    endpoint_id = UnicodeAttribute(hash_key=True)
    data_source_type = UnicodeAttribute(range_key=True)


class DataSourceModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-data_sources"

    endpoint_id = UnicodeAttribute(hash_key=True)
    data_source_name = UnicodeAttribute(range_key=True)
    data_source_type = UnicodeAttribute()
    module_name = UnicodeAttribute()
    class_name = UnicodeAttribute()
    configuration = MapAttribute()
    data_views = ListAttribute(of=MapAttribute, null=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    data_source_type_index = DataSourceTypeIndex()


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


def get_data_source_type(
    info: ResolveInfo, data_source: DataSourceModel
) -> DataSourceType:
    data_source = data_source.__dict__["attribute_values"]
    return DataSourceType(**Utility.json_loads(Utility.json_dumps(data_source)))


def resolve_data_source(
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
def resolve_data_source_list(
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
def insert_update_data_source(
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
def delete_data_source(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
