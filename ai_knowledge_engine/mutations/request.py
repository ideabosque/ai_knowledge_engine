#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Int, Mutation, String, List
from silvaengine_utility import JSON

from ..models.request import insert_update_request, delete_request
from ..types.request import RequestType
from ..handlers.collector import S3DataProcessor
from ..handlers.shopify import ShopifyHandler


class InsertUpdateRequest(Mutation):
    request = Field(RequestType)

    class Arguments:
        document_source = String(required=True)
        request_uuid = String(required=False)
        user_query = String(required=False)
        cypher_query = String(required=False)
        is_similarity_search = Boolean(required=False)
        result = List(JSON, required=False)
        request_note = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateRequest":
        try:
            request = insert_update_request(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateRequest(request=request)


class DeleteRequest(Mutation):
    ok = Boolean()

    class Arguments:
        document_source = String(required=True)
        request_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteRequest":
        try:
            ok = delete_request(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteRequest(ok=ok)


class LoadDocument(Mutation):
    ok = Boolean()

    class Arguments:
        document_source = String(required=True)
        endpoint_id = String(required=True)
        object_key = String(required=True)
        position = Int(required=False,default_value=0)
        skip_header = Boolean(required=False,default_value=True)
        embedding_attributes = List(String, required=False, default_value=[])
        graph_scheme_attributes = JSON(required=False, default_value={})
        vector_scheme_attributes = JSON(required=False, default_value={})
        max_retries = Int(required=False, default_value=3)
        editor = String(required=False, default_value="")
        chunk_size_for_unstructured = Int(required=False, default_value=500)
        document_external_id = String(required=False, default_value=None)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateRequest":
        try:
            print(kwargs)
            S3DataProcessor(setting=info.context.get("setting", {})).process_file(info=info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return LoadDocument(ok=True)


class LoadShopifyDocument(Mutation):
    ok = Boolean()

    class Arguments:
        document_source = String(required=True)
        endpoint_id = String(required=True)
        position = Int(required=False,default_value=0)
        embedding_attributes = List(String, required=False, default_value=[])
        graph_scheme_attributes = JSON(required=False, default_value={})
        vector_scheme_attributes = JSON(required=False, default_value={})
        max_retries = Int(required=False, default_value=3)
        editor = String(required=False, default_value="")
        document_external_id = String(required=False, default_value=None)
        filters = JSON(required=False, default_value={})

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateRequest":
        try:
            ShopifyHandler(setting=info.context.get("setting", {}), logger=info.context.get("logger")).process_data(info=info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return LoadDocument(ok=True)
