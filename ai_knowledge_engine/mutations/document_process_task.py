#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field,  Mutation, String, DateTime

from ..models.document_process_task import insert_update_document_process_task, delete_document_process_task
from ..types.document_process_task import DocumentProcessTaskType


class InsertUpdateDocumentProcessTask(Mutation):
    document_process_task = Field(DocumentProcessTaskType)

    class Arguments:
        document_source = String(required=True)
        process_task_uuid = String(required=False)
        process_status = String(required=False)
        process_note = String(required=False)
        cut_time = DateTime(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateDocumentProcessTask":
        try:
            document_process_task = insert_update_document_process_task(
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
        document_source = String(required=True)
        process_task_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteDocumentProcessTask":
        try:
            ok = delete_document_process_task(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteDocumentProcessTask(ok=ok)
