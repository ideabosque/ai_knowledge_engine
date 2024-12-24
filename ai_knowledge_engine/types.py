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
    document_source = String()
    document_uuid = String()
    document_external_id = String()
    document_type = String()
    document_title = String()
    document_content = String()
    title_embedding = List(Float)
    content_embedding = List(Float)
    log = String()
    status = String()
    updated_by = String()
    updated_at = DateTime()
    created_at = DateTime()


class DocumentSourceType(ObjectType):
    document_type = String()
    document_source = String()
    module_name = String()
    class_name = String()
    configuration = JSON()
    updated_by = String()
    updated_at = DateTime()
    created_at = DateTime()


class DocumentProcessTaskType(ObjectType):
    document_source = String()
    process_task_uuid = String()
    document_type = String()
    process_status = String()
    process_note = String()
    cut_time = DateTime()
    start_time = DateTime()
    end_time = DateTime()


class KnowledgeGraphMetadataType(ObjectType):
    document_type = String()
    metadata_version_uuid = String()
    document_source = String()
    data_source_name = String()
    data_source_type = String()
    data_view_name = String()
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


class DocumentSourceListType(ListObjectType):
    document_source_list = List(DocumentSourceType)


class DocumentProcessTaskListType(ListObjectType):
    document_process_task_list = List(DocumentProcessTaskType)


class KnowledgeGraphMetadataListType(ListObjectType):
    knowledge_graph_metadata_list = List(KnowledgeGraphMetadataType)


class DataSourceListType(ListObjectType):
    data_source_list = List(DataSourceType)
