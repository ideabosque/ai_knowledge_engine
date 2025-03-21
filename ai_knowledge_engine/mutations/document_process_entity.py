#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field,  Mutation, String, DateTime

from ..models.document_process_entity import insert_update_document_process_entity, delete_document_process_entity
from ..types.document_process_entity import DocumentProcessEntityType


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
            document_process_entity = insert_update_document_process_entity(
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
            ok = delete_document_process_entity(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteDocumentProcessEntity(ok=ok)

