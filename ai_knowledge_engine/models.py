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


class DocumentSourceIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "document_source-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    document_type = UnicodeAttribute(hash_key=True)
    document_source = UnicodeAttribute(range_key=True)


class DocumentExternalIdIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "document_external_id-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    document_type = UnicodeAttribute(hash_key=True)
    document_external_id = UnicodeAttribute(range_key=True)


class DocumentModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-documents"

    document_type = UnicodeAttribute(hash_key=True)
    document_uuid = UnicodeAttribute(range_key=True)
    document_source = UnicodeAttribute()
    document_external_id = UnicodeAttribute()
    document_title = UnicodeAttribute()
    document_content = UnicodeAttribute()
    title_embedding = ListAttribute(of=NumberAttribute, default=[])
    content_embedding = ListAttribute(of=NumberAttribute, default=[])
    log = UnicodeAttribute(null=True)
    status = UnicodeAttribute(default="initial")
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    document_source_index = DocumentSourceIndex()
    document_external_id_index = DocumentExternalIdIndex()


class DocumentSourceModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-document_sources"

    document_type = UnicodeAttribute(hash_key=True)
    document_source = UnicodeAttribute(range_key=True)
    module_name = UnicodeAttribute()
    class_name = UnicodeAttribute()
    configuration = MapAttribute()
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()


class DocumentProcessTaskDocumentSourceIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "document_source-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    document_type = UnicodeAttribute(hash_key=True)
    document_source = UnicodeAttribute(range_key=True)


class DocumentProcessTaskModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-document_process_tasks"

    document_type = UnicodeAttribute(hash_key=True)
    process_task_uuid = UnicodeAttribute(range_key=True)
    document_source = UnicodeAttribute()
    entities = ListAttribute(of=MapAttribute)
    process_status = UnicodeAttribute(default="initial")
    process_note = UnicodeAttribute(null=True)
    cut_time = UTCDateTimeAttribute(null=True)
    start_time = UTCDateTimeAttribute()
    end_time = UTCDateTimeAttribute(null=True)
    document_source_index = DocumentProcessTaskDocumentSourceIndex()


class KnowledgeGraphMetadataDocumentSourceIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "document_source-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    document_type = UnicodeAttribute(hash_key=True)
    document_source = UnicodeAttribute(range_key=True)


class KnowledgeGraphMetadataModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-knowledge_graph_metadata"

    document_type = UnicodeAttribute(hash_key=True)
    metadata_version_uuid = UnicodeAttribute(range_key=True)
    document_source = UnicodeAttribute()
    data_source_name = UnicodeAttribute()
    data_source_type = UnicodeAttribute()
    data_view_name = UnicodeAttribute()
    structured_fields = ListAttribute(of=MapAttribute, default=[])
    unstructured_attributes = ListAttribute(of=MapAttribute, default=[])
    linkage_rules = ListAttribute(of=MapAttribute, default=[])
    status = BooleanAttribute(default=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    document_source_index = KnowledgeGraphMetadataDocumentSourceIndex()


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
