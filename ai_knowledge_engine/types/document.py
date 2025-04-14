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


class DocumentType(ObjectType):
    document_source = JSON()
    document_uuid = String()
    document_external_id = String()
    chunk_index = Int()
    document_title = String()
    document_content = String()
    title_embedding = List(Float)
    content_embedding = List(Float)
    updated_by = String()
    updated_at = DateTime()
    created_at = DateTime()


class DocumentListType(ListObjectType):
    document_list = List(DocumentType)