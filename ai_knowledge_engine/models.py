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
    endpoint_id = UnicodeAttribute()
    document_title = UnicodeAttribute()
    document_content = UnicodeAttribute()
    title_embedding = ListAttribute(of=NumberAttribute, null=True)
    content_embedding = ListAttribute(of=NumberAttribute, null=True)
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    document_external_id_index = DocumentExternalIdIndex()


class DocumentProcessTaskModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-document_process_tasks"

    document_source = UnicodeAttribute(hash_key=True)
    process_task_uuid = UnicodeAttribute(range_key=True)
    endpoint_id = UnicodeAttribute()
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
    logs = ListAttribute(of=MapAttribute, null=True)
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
    endpoint_id = UnicodeAttribute()
    structured_data_views = ListAttribute(of=MapAttribute, null=True)
    structured_fields = ListAttribute(of=MapAttribute, null=True)
    unstructured_attributes = ListAttribute(of=MapAttribute, null=True)
    linkage_rules = ListAttribute(of=MapAttribute, null=True)
    merge_rule = MapAttribute(null=True)
    status = BooleanAttribute(default=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()


class DataSourceTypeIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "data_source_type-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    endpoint_id = UnicodeAttribute(hash_key=True)
    data_source_type = UnicodeAttribute(range_key=True)


class DataSourceModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-data_sources"

    endpoint_id = UnicodeAttribute(hash_key=True)
    data_source_name = UnicodeAttribute(range_key=True)
    data_source_type = UnicodeAttribute()
    module_name = UnicodeAttribute()
    class_name = UnicodeAttribute()
    configuration = MapAttribute()
    data_views = ListAttribute(of=MapAttribute, null=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    data_source_type_index = DataSourceTypeIndex()


class RequestModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-requests"

    document_source = UnicodeAttribute(hash_key=True)
    request_uuid = UnicodeAttribute(range_key=True)
    user_query = UnicodeAttribute()
    cypher_query = UnicodeAttribute(null=True)
    is_similarity_search = BooleanAttribute(default=False)
    results = ListAttribute(of=MapAttribute, null=True)
    request_note = UnicodeAttribute(null=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
