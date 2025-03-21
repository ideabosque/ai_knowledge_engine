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


class DocumentProcessEntityType(ObjectType):
    document_process_task = JSON()
    document_entity_uuid = String()
    document_external_id = String()
    document_version = String()
    logs = List(JSON)
    status = String()
    updated_by = String()
    updated_at = DateTime()
    created_at = DateTime()


class DocumentProcessEntityListType(ListObjectType):
    document_process_entity_list = List(DocumentProcessEntityType)
