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


class KnowledgeGraphMetadataType(ObjectType):
    document_source = JSON()
    metadata_version_uuid = String()
    structured_data_views = List(JSON)
    structured_fields = List(JSON)
    unstructured_attributes = List(JSON)
    linkage_rules = List(JSON)
    merge_rule = JSON()
    status = Boolean()
    updated_by = String()
    updated_at = DateTime()
    created_at = DateTime()


class KnowledgeGraphMetadataListType(ListObjectType):
    knowledge_graph_metadata_list = List(KnowledgeGraphMetadataType)
