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

from silvaengine_utility import JSON

from .mutations import (
    DeleteDataSource,
    DeleteDocument,
    DeleteDocumentProcessEntity,
    DeleteDocumentProcessTask,
    DeleteKnowledgeGraphMetadata,
    DeleteRequest,
    InsertUpdateDataSource,
    InsertUpdateDocument,
    InsertUpdateDocumentProcessEntity,
    InsertUpdateDocumentProcessTask,
    InsertUpdateKnowledgeGraphMetadata,
    InsertUpdateRequest,
    LoadDocument,
)
from .queries import (
    resolve_data_source,
    resolve_data_source_list,
    resolve_data_view,
    resolve_document,
    resolve_document_list,
    resolve_document_process_entity,
    resolve_document_process_entity_list,
    resolve_document_process_task,
    resolve_document_process_task_list,
    resolve_knowledge_graph_metadata,
    resolve_knowledge_graph_metadata_list,
    resolve_knowledge_rag,
    resolve_request,
    resolve_request_list,
)
from .types import (
    DataSourceListType,
    DataSourceType,
    DataViewType,
    DocumentListType,
    DocumentProcessEntityListType,
    DocumentProcessEntityType,
    DocumentProcessTaskListType,
    DocumentProcessTaskType,
    DocumentType,
    KnowledgeGraphMetadataListType,
    KnowledgeGraphMetadataType,
    KnowledgeRagType,
    RequestListType,
    RequestType,
)


def type_class():
    return [
        DataSourceListType,
        DataSourceType,
        DocumentListType,
        DocumentProcessTaskListType,
        DocumentProcessTaskType,
        DocumentType,
        KnowledgeGraphMetadataListType,
        KnowledgeGraphMetadataType,
        DocumentProcessEntityType,
        DocumentProcessEntityListType,
        RequestType,
        RequestListType,
        KnowledgeRagType,
        DataViewType,
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
        document_external_id=String(required=False),
        document_types=List(String, required=False),
        document_title=String(required=False),
        document_content=String(required=False),
        statuses=List(String, required=False),
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

    document_process_entity = Field(
        DocumentProcessEntityType,
        process_task_uuid=String(required=True),
        document_entity_uuid=String(required=True),
    )

    document_process_entity_list = Field(
        DocumentProcessEntityListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        process_task_uuid=String(required=False),
        document_external_id=String(required=False),
        document_sources=List(String, required=False),
        document_version=String(required=False),
    )

    knowledge_graph_metadata = Field(
        KnowledgeGraphMetadataType,
        document_source=String(required=True),
        metadata_version_uuid=String(required=False),
    )

    knowledge_graph_metadata_list = Field(
        KnowledgeGraphMetadataListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        document_source=String(required=False),
        status=String(required=False),
    )

    data_source = Field(
        DataSourceType,
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

    request = Field(
        RequestType,
        document_source=String(required=True),
        request_uuid=String(required=True),
    )

    request_list = Field(
        RequestListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        document_source=String(required=False),
        user_inquiry=String(required=False),
        cypher_query=String(required=False),
        is_similarity_search=Boolean(required=False),
    )

    knowledge_rag = Field(
        KnowledgeRagType,
        user_query=String(required=True),
        document_source=String(required=False),
        is_similarity_search=Boolean(required=False),
        hybrid_fields=List(String, required=False),
        offset=Int(required=False),
        limit=Int(required=False),
        k=Int(required=False),
    )

    data_view = Field(
        DataViewType,
        data_source_type=String(required=True),
        data_source_name=String(required=True),
        data_view_name=String(required=True),
        parameters=JSON(required=False),
    )

    def resolve_ping(self, info: ResolveInfo) -> str:
        return f"Hello at {time.strftime('%X')}!!"

    def resolve_document(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DocumentType:
        return resolve_document(info, **kwargs)

    def resolve_document_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DocumentListType:
        return resolve_document_list(info, **kwargs)

    def resolve_document_process_task(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DocumentProcessTaskType:
        return resolve_document_process_task(info, **kwargs)

    def resolve_document_process_task_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DocumentProcessTaskListType:
        return resolve_document_process_task_list(info, **kwargs)

    def resolve_document_process_entity(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DocumentProcessEntityType:
        return resolve_document_process_entity(info, **kwargs)

    def resolve_document_process_entity_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DocumentProcessEntityListType:
        return resolve_document_process_entity_list(info, **kwargs)

    def resolve_knowledge_graph_metadata(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> KnowledgeGraphMetadataType:
        return resolve_knowledge_graph_metadata(info, **kwargs)

    def resolve_knowledge_graph_metadata_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> KnowledgeGraphMetadataListType:
        return resolve_knowledge_graph_metadata_list(info, **kwargs)

    def resolve_data_source(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DataSourceType:
        return resolve_data_source(info, **kwargs)

    def resolve_data_source_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DataSourceListType:
        return resolve_data_source_list(info, **kwargs)

    def resolve_request(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> RequestType:
        return resolve_request(info, **kwargs)

    def resolve_request_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> RequestListType:
        return resolve_request_list(info, **kwargs)

    def resolve_knowledge_rag(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> KnowledgeRagType:
        return resolve_knowledge_rag(info, **kwargs)

    def resolve_data_view(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DataViewType:
        return resolve_data_view(info, **kwargs)


class Mutations(ObjectType):
    insert_update_document = InsertUpdateDocument.Field()
    delete_document = DeleteDocument.Field()
    insert_update_document_process_task = InsertUpdateDocumentProcessTask.Field()
    delete_document_process_task = DeleteDocumentProcessTask.Field()
    insert_update_document_process_entity = InsertUpdateDocumentProcessEntity.Field()
    delete_document_process_entity = DeleteDocumentProcessEntity.Field()
    insert_update_knowledge_graph_metadata = InsertUpdateKnowledgeGraphMetadata.Field()
    delete_knowledge_graph_metadata = DeleteKnowledgeGraphMetadata.Field()
    insert_update_data_source = InsertUpdateDataSource.Field()
    delete_data_source = DeleteDataSource.Field()
    insert_update_request = InsertUpdateRequest.Field()
    delete_request = DeleteRequest.Field()
    load_document = LoadDocument.Field()
