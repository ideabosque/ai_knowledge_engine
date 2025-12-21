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


class ShortTermMemoryType(ObjectType):
    user_uuid = String()
    memory_uuid = String()
    message_uuid = String()
    thread_uuid = String()
    profile = JSON()
    entities = List(JSON)
    preferences = List(JSON)
    interests = List(JSON)
    needs = List(JSON)
    message_time = DateTime()
    created_at = DateTime()
    updated_at = DateTime()
    confidence = Float()
    status = String()
    ltm_version_id = String()


class ShortTermMemoryListType(ListObjectType):
    short_term_memory_list = List(ShortTermMemoryType)
