#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Float, List, Mutation, String

from ..models.document import insert_update_document, delete_document
from ..types.document import DocumentType

class InsertUpdateDocument(Mutation):
    document = Field(DocumentType)

    class Arguments:
        document_source = String(required=True)
        document_uuid = String(required=False)
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
            document = insert_update_document(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateDocument(document=document)


class DeleteDocument(Mutation):
    ok = Boolean()

    class Arguments:
        document_source = String(required=True)
        document_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteDocument":
        try:
            ok = delete_document(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteDocument(ok=ok)
