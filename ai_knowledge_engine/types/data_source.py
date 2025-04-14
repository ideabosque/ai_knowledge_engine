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


class DataSourceType(ObjectType):
    endpoint_id = String()
    data_source_name = String()
    data_source_type = String()
    module_name = String()
    class_name = String()
    configuration = JSON()
    data_views = List(JSON)
    updated_by = String()
    updated_at = DateTime()
    created_at = DateTime()


class DataSourceListType(ListObjectType):
    data_source_list = List(DataSourceType)
