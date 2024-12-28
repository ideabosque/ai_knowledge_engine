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


class DocumentProcessTaskType(ObjectType):
    document_source = JSON()
    process_task_uuid = String()
    process_status = String()
    process_note = String()
    cut_time = DateTime()
    start_time = DateTime()
    end_time = DateTime()


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


class KnowledgeGraphMetadataType(ObjectType):
    document_source = JSON()
    metadata_version_uuid = String()
    structured_data_views = List(JSON)
    structured_fields = List(JSON)
    unstructured_attributes = List(JSON)
    linkage_rules = List(JSON)
    status = Boolean()
    updated_by = String()
    updated_at = DateTime()
    created_at = DateTime()


class DataSourceType(ObjectType):
    data_source_type = String()
    data_source_name = String()
    module_name = String()
    class_name = String()
    configuration = JSON()
    data_views = List(JSON)
    updated_by = String()
    updated_at = DateTime()
    created_at = DateTime()


class DocumentListType(ListObjectType):
    document_list = List(DocumentType)


class DocumentProcessTaskListType(ListObjectType):
    document_process_task_list = List(DocumentProcessTaskType)


class DocumentProcessEntityListType(ListObjectType):
    document_process_entity_list = List(DocumentProcessEntityType)


class KnowledgeGraphMetadataListType(ListObjectType):
    knowledge_graph_metadata_list = List(KnowledgeGraphMetadataType)


class DataSourceListType(ListObjectType):
    data_source_list = List(DataSourceType)
