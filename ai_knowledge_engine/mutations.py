#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, DateTime, Field, Float, Int, List, Mutation, String

from silvaengine_utility import JSON

from .handlers import (
    delete_data_source_handler,
    delete_document_handler,
    delete_document_process_entity_handler,
    delete_document_process_task_handler,
    delete_knowledge_graph_metadata_handler,
    insert_update_data_source_handler,
    insert_update_document_handler,
    insert_update_document_process_entity_handler,
    insert_update_document_process_task_handler,
    insert_update_knowledge_graph_metadata_handler,
)
from .types import (
    DataSourceType,
    DocumentProcessEntityType,
    DocumentProcessTaskType,
    DocumentType,
    KnowledgeGraphMetadataType,
)


class InsertUpdateDocument(Mutation):
    document = Field(DocumentType)

    class Arguments:
        document_type = String(required=True)
        document_uuid = String(required=False)
        document_source = String(required=False)
        document_external_id = String(required=False)
        document_title = String(required=False)
        document_content = String(required=False)
        title_embedding = List(Float, required=False)
        content_embedding = List(Float, required=False)
        log = String(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateDocument":
        try:
            document = insert_update_document_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateDocument(document=document)


class DeleteDocument(Mutation):
    ok = Boolean()

    class Arguments:
        document_type = String(required=True)
        document_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteDocument":
        try:
            ok = delete_document_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteDocument(ok=ok)


class InsertUpdateDocumentProcessTask(Mutation):
    document_process_task = Field(DocumentProcessTaskType)

    class Arguments:
        document_source = String(required=True)
        process_task_uuid = String(required=False)
        document_type = String(required=False)
        process_status = String(required=False)
        process_note = String(required=False)
        cut_time = DateTime(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateDocumentProcessTask":
        try:
            document_process_task = insert_update_document_process_task_handler(
                info, **kwargs
            )
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateDocumentProcessTask(
            document_process_task=document_process_task
        )


class DeleteDocumentProcessTask(Mutation):
    ok = Boolean()

    class Arguments:
        document_type = String(required=True)
        process_task_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteDocumentProcessTask":
        try:
            ok = delete_document_process_task_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteDocumentProcessTask(ok=ok)


class InsertUpdateDocumentProcessEntity(Mutation):
    document_process_entity = Field(DocumentProcessEntityType)

    class Arguments:
        process_task_uuid = String(required=True)
        document_entity_uuid = String(required=False)
        document_external_id = String(required=False)
        document_source = String(required=False)
        document_version = String(required=False)
        log = String(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateDocumentProcessEntity":
        try:
            document_process_entity = insert_update_document_process_entity_handler(
                info, **kwargs
            )
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateDocumentProcessEntity(
            document_process_entity=document_process_entity
        )


class DeleteDocumentProcessEntity(Mutation):
    ok = Boolean()

    class Arguments:
        process_task_uuid = String(required=True)
        document_entity_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteDocumentProcessEntity":
        try:
            ok = delete_document_process_entity_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteDocumentProcessEntity(ok=ok)


class InsertUpdateKnowledgeGraphMetadata(Mutation):
    knowledge_graph_metadata = Field(KnowledgeGraphMetadataType)

    class Arguments:
        document_type = String(required=True)
        metadata_version_uuid = String(required=False)
        document_source = String(required=False)
        structured_data_views = List(JSON, required=False)
        structured_fields = List(JSON, required=False)
        unstructured_attributes = List(JSON, required=False)
        linkage_rules = List(JSON, required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateKnowledgeGraphMetadata":
        try:
            knowledge_graph_metadata = insert_update_knowledge_graph_metadata_handler(
                info, **kwargs
            )
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateKnowledgeGraphMetadata(
            knowledge_graph_metadata=knowledge_graph_metadata
        )


class DeleteKnowledgeGraphMetadata(Mutation):
    ok = Boolean()

    class Arguments:
        document_type = String(required=True)
        metadata_version_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteKnowledgeGraphMetadata":
        try:
            ok = delete_knowledge_graph_metadata_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteKnowledgeGraphMetadata(ok=ok)


class InsertUpdateDataSource(Mutation):
    data_source = Field(DataSourceType)

    class Arguments:
        data_source_type = String(required=True)
        data_source_name = String(required=False)
        module_name = String(required=False)
        class_name = String(required=False)
        configuration = JSON(required=False)
        data_views = List(JSON, required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateDataSource":
        try:
            data_source = insert_update_data_source_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateDataSource(data_source=data_source)


class DeleteDataSource(Mutation):
    ok = Boolean()

    class Arguments:
        data_source_type = String(required=True)
        data_source_name = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteDataSource":
        try:
            ok = delete_data_source_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteDataSource(ok=ok)
