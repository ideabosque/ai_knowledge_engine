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


class LongTermMemoryType(ObjectType):
    user_uuid = String()
    ltm_version_id = String()
    profile = JSON()
    interests = List(JSON)
    preferences = List(JSON)
    needs = List(JSON)
    create_log = JSON()
    last_stm_time = DateTime()
    created_at = DateTime()
    updated_at = DateTime()


class LongTermMemoryListType(ListObjectType):
    long_term_memory_list = List(LongTermMemoryType)

