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
from ..types.request import RequestType, RequestListType
from .utils import _get_data_source


class RequestModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-requests"

    document_source = UnicodeAttribute(hash_key=True)
    request_uuid = UnicodeAttribute(range_key=True)
    user_query = UnicodeAttribute()
    cypher_query = UnicodeAttribute(null=True)
    is_similarity_search = BooleanAttribute(default=False)
    results = ListAttribute(of=MapAttribute, null=True)
    request_note = UnicodeAttribute(null=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()


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


def resolve_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> RequestType:
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
def resolve_request_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
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
def insert_update_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
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
def delete_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
