#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import time
from typing import Any, Dict

from graphene import (
    Boolean,
    DateTime,
    Field,
    Int,
    List,
    ObjectType,
    ResolveInfo,
    String,
)

from .mutations import (
    DeleteDataSource,
    DeleteDocument,
    DeleteDocumentProcessTask,
    DeleteDocumentSource,
    DeleteKnowledgeGraphMetadata,
    InsertUpdateDataSource,
    InsertUpdateDocument,
    InsertUpdateDocumentProcessTask,
    InsertUpdateDocumentSource,
    InsertUpdateKnowledgeGraphMetadata,
)
from .queries import (
    resolve_data_source,
    resolve_data_source_list,
    resolve_document,
    resolve_document_list,
    resolve_document_process_task,
    resolve_document_process_task_list,
    resolve_document_source,
    resolve_document_source_list,
    resolve_knowledge_graph_metadata,
    resolve_knowledge_graph_metadata_list,
)
from .types import (
    DataSourceListType,
    DataSourceType,
    DocumentListType,
    DocumentProcessTaskListType,
    DocumentProcessTaskType,
    DocumentSourceListType,
    DocumentSourceType,
    DocumentType,
    KnowledgeGraphMetadataListType,
    KnowledgeGraphMetadataType,
)


def type_class():
    return [
        DataSourceListType,
        DataSourceType,
        DocumentListType,
        DocumentProcessTaskListType,
        DocumentProcessTaskType,
        DocumentSourceListType,
        DocumentSourceType,
        DocumentType,
        KnowledgeGraphMetadataListType,
        KnowledgeGraphMetadataType,
    ]


class Query(ObjectType):
    ping = String()

    document = Field(
        DocumentType,
        document_source=String(required=True),
        document_uuid=String(required=True),
    )

    document_list = Field(
        DocumentListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        document_source=String(required=False),
        document_types=List(String, required=False),
        document_list=String(required=False),
        document_content=String(required=False),
        statuses=List(String, required=False),
    )

    document_source = Field(
        DocumentSourceType,
        document_type=String(required=True),
        document_source=String(required=True),
    )

    document_source_list = Field(
        DocumentSourceListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        document_type=String(required=False),
        module_name=String(required=False),
        class_name=String(required=False),
    )

    document_process_task = Field(
        DocumentProcessTaskType,
        document_source=String(required=True),
        process_task_uuid=String(required=True),
    )

    document_process_task_list = Field(
        DocumentProcessTaskListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        document_source=String(required=False),
        document_types=List(String, required=False),
        process_statuses=List(String, required=False),
    )

    knowledge_graph_metadata = Field(
        KnowledgeGraphMetadataType,
        document_type=String(required=True),
        metadata_version_uuid=String(required=True),
    )

    knowledge_graph_metadata_list = Field(
        KnowledgeGraphMetadataListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        document_type=String(required=False),
        document_sources=List(String, required=False),
        data_source_name=String(required=False),
        data_source_types=List(String, required=False),
        data_view_name=String(required=False),
        status=String(required=False),
    )

    data_source = Field(
        DataSourceType,
        data_source_type=String(required=True),
        data_source_name=String(required=True),
    )

    data_source_list = Field(
        DataSourceListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        data_source_type=String(required=False),
        module_name=String(required=False),
        class_name=String(required=False),
    )

    def resolve_ping(self, info: ResolveInfo) -> str:
        return f"Hello at {time.strftime('%X')}!!"

    def resolve_document(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
        return resolve_document(info, **kwargs)

    def resolve_document_list(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
        return resolve_document_list(info, **kwargs)

    def resolve_document_source(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> Any:
        return resolve_document_source(info, **kwargs)

    def resolve_document_source_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> Any:
        return resolve_document_source_list(info, **kwargs)

    def resolve_document_process_task(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> Any:
        return resolve_document_process_task(info, **kwargs)

    def resolve_document_process_task_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> Any:
        return resolve_document_process_task_list(info, **kwargs)

    def resolve_knowledge_graph_metadata(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> Any:
        return resolve_knowledge_graph_metadata(info, **kwargs)

    def resolve_knowledge_graph_metadata_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> Any:
        return resolve_knowledge_graph_metadata_list(info, **kwargs)

    def resolve_data_source(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
        return resolve_data_source(info, **kwargs)

    def resolve_data_source_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> Any:
        return resolve_data_source_list(info, **kwargs)


class Mutations(ObjectType):
    insert_update_document = InsertUpdateDocument.Field()
    delete_document = DeleteDocument.Field()
    insert_update_document_source = InsertUpdateDocumentSource.Field()
    delete_document_source = DeleteDocumentSource.Field()
    insert_update_document_process_task = InsertUpdateDocumentProcessTask.Field()
    delete_document_process_task = DeleteDocumentProcessTask.Field()
    insert_update_knowledge_graph_metadata = InsertUpdateKnowledgeGraphMetadata.Field()
    delete_knowledge_graph_metadata = DeleteKnowledgeGraphMetadata.Field()
    insert_update_data_source = InsertUpdateDataSource.Field()
    delete_data_source = DeleteDataSource.Field()
