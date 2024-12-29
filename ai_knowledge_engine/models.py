#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from pynamodb.attributes import (
    BooleanAttribute,
    ListAttribute,
    MapAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
from pynamodb.indexes import AllProjection, LocalSecondaryIndex

from silvaengine_dynamodb_base import BaseModel


class DocumentExternalIdIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "document_external_id-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    document_source = UnicodeAttribute(hash_key=True)
    document_external_id = UnicodeAttribute(range_key=True)


class DocumentModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-documents"

    document_source = UnicodeAttribute(hash_key=True)
    document_uuid = UnicodeAttribute(range_key=True)
    document_external_id = UnicodeAttribute()
    chunk_index = NumberAttribute(default=0)
    document_type = UnicodeAttribute()
    document_title = UnicodeAttribute()
    document_content = UnicodeAttribute()
    title_embedding = ListAttribute(of=NumberAttribute, default=[])
    content_embedding = ListAttribute(of=NumberAttribute, default=[])
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    document_external_id_index = DocumentExternalIdIndex()


class DocumentProcessTaskModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-document_process_tasks"

    document_source = UnicodeAttribute(hash_key=True)
    process_task_uuid = UnicodeAttribute(range_key=True)
    document_type = UnicodeAttribute()
    process_status = UnicodeAttribute(default="initial")
    process_note = UnicodeAttribute(null=True)
    cut_time = UTCDateTimeAttribute(null=True)
    start_time = UTCDateTimeAttribute()
    end_time = UTCDateTimeAttribute(null=True)


class DocumentProcessEntityDocumentExternalIdIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "document_external_id-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    process_task_uuid = UnicodeAttribute(hash_key=True)
    document_external_id = UnicodeAttribute(range_key=True)


class DocumentProcessEntityModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-document_process_entities"

    process_task_uuid = UnicodeAttribute(hash_key=True)
    document_entity_uuid = UnicodeAttribute(range_key=True)
    document_external_id = UnicodeAttribute()
    document_source = UnicodeAttribute()
    document_version = UnicodeAttribute()
    logs = ListAttribute(of=MapAttribute, default=[])
    status = UnicodeAttribute(default="initial")
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    document_external_id_index = DocumentProcessEntityDocumentExternalIdIndex()


class KnowledgeGraphMetadataModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-knowledge_graph_metadata"

    document_source = UnicodeAttribute(hash_key=True)
    metadata_version_uuid = UnicodeAttribute(range_key=True)
    document_type = UnicodeAttribute()
    structured_data_views = ListAttribute(of=MapAttribute, default=[])
    structured_fields = ListAttribute(of=MapAttribute, default=[])
    unstructured_attributes = ListAttribute(of=MapAttribute, default=[])
    linkage_rules = ListAttribute(of=MapAttribute, default=[])
    status = BooleanAttribute(default=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()


class DataSourceModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-data_sources"

    data_source_type = UnicodeAttribute(hash_key=True)
    data_source_name = UnicodeAttribute(range_key=True)
    module_name = UnicodeAttribute()
    class_name = UnicodeAttribute()
    configuration = MapAttribute()
    data_views = ListAttribute(of=MapAttribute, default=[])
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()


class RequestModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-requests"

    data_source_name = UnicodeAttribute(hash_key=True)
    request_uuid = UnicodeAttribute(range_key=True)
    data_source_type = UnicodeAttribute()
    user_inquiry = UnicodeAttribute()
    generated_query = UnicodeAttribute(null=True)
    result = ListAttribute(of=MapAttribute, default=[])
    request_note = UnicodeAttribute(null=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
