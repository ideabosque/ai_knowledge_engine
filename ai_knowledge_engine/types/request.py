#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import (
    Boolean,
    DateTime,
    Decimal,
    Field,
    Float,
    Int,
    List,
    ObjectType,
    String,
)

from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class RequestType(ObjectType):
    document_source = String()
    request_uuid = String()
    user_query = String()
    cypher_query = String()
    is_similarity_search = Boolean()
    results = List(JSON)
    request_note = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class RequestListType(ListObjectType):
    request_list = List(RequestType)
