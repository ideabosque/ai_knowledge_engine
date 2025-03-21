#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field,  Mutation, String, List
from silvaengine_utility import JSON

from ..models.knowledge_graph_metadata import insert_update_knowledge_graph_metadata, delete_knowledge_graph_metadata
from ..types.knowledge_graph_metadata import KnowledgeGraphMetadataType


class InsertUpdateKnowledgeGraphMetadata(Mutation):
    knowledge_graph_metadata = Field(KnowledgeGraphMetadataType)

    class Arguments:
        document_source = String(required=True)
        metadata_version_uuid = String(required=False)
        structured_data_views = List(JSON, required=False)
        structured_fields = List(JSON, required=False)
        unstructured_attributes = List(JSON, required=False)
        linkage_rules = List(JSON, required=False)
        merge_rule = JSON(required=False)
        status = Boolean(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateKnowledgeGraphMetadata":
        try:
            knowledge_graph_metadata = insert_update_knowledge_graph_metadata(
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
        document_source = String(required=True)
        metadata_version_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteKnowledgeGraphMetadata":
        try:
            ok = delete_knowledge_graph_metadata(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteKnowledgeGraphMetadata(ok=ok)
