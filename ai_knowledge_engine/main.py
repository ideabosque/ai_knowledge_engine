#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
from typing import Any, Dict, List

from graphene import Schema

from silvaengine_dynamodb_base import SilvaEngineDynamoDBBase

from .handlers import handlers_init
from .schema import Mutations, Query, type_class


def deploy() -> List:
    return [
        {
            "service": "AI Assistant",
            "class": "AIKnowledgeEngine",
            "functions": {
                "ai_knowledge_graphql": {
                    "is_static": False,
                    "label": "AI Knowledge GraphQL",
                    "query": [
                        {"action": "document", "label": "View Document"},
                        {"action": "documentList", "label": "View Document List"},
                        {
                            "action": "document_process_task",
                            "label": "View Document Process Task",
                        },
                        {
                            "action": "documentProcessTaskList",
                            "label": "View Document Process Task List",
                        },
                        {
                            "action": "documentProcessEntity",
                            "label": "View Document Process Entity",
                        },
                        {
                            "action": "documentProcessEntityList",
                            "label": "View Document Process Entity List",
                        },
                        {
                            "action": "knowledgeGraphMetadata",
                            "label": "View Knowledge Graph Metadata",
                        },
                        {
                            "action": "knowledgeGraphMetadataList",
                            "label": "View Knowledge Graph Metadata List",
                        },
                        {"action": "dataSource", "label": "View Data Source"},
                        {"action": "dataSourceList", "label": "View Data Source List"},
                        {"action": "request", "label": "View Request"},
                        {"action": "requestList", "label": "View Request List"},
                        {"action": "knowledgeRag", "label": "View Knowledge RAG"},
                        {
                            "action": "knowledgeRagList",
                            "label": "View Knowledge RAG List",
                        },
                        {"action": "dataView", "label": "View Data View"},
                        {"action": "dataViewList", "label": "View Data View List"},
                    ],
                    "mutation": [
                        {
                            "action": "insertUpdateDocument",
                            "label": "Insert Update Document",
                        },
                        {"action": "deleteDocument", "label": "Delete Document"},
                        {
                            "action": "insertUpdateDocumentProcessTask",
                            "label": "Insert Update Document Process Task",
                        },
                        {
                            "action": "deleteDocumentProcessTask",
                            "label": "Delete Document Process Task",
                        },
                        {
                            "action": "insertUpdateDocumentProcessEntity",
                            "label": "Insert Update Document Process Entity",
                        },
                        {
                            "action": "deleteDocumentProcessEntity",
                            "label": "Delete Document Process Entity",
                        },
                        {
                            "action": "insertUpdateKnowledgeGraphMetadata",
                            "label": "Insert Update Knowledge Graph Metadata",
                        },
                        {
                            "action": "deleteKnowledgeGraphMetadata",
                            "label": "Delete Knowledge Graph Metadata",
                        },
                        {
                            "action": "insertUpdateDataSource",
                            "label": "Insert Update Data Source",
                        },
                        {"action": "deleteDataSource", "label": "Delete Data Source"},
                        {
                            "action": "insertUpdateRequest",
                            "label": "Insert Update Request",
                        },
                        {"action": "deleteRequest", "label": "Delete Request"},
                        {
                            "action": "insertUpdateKnowledgeRag",
                            "label": "Insert Update Knowledge RAG",
                        },
                        {
                            "action": "deleteKnowledgeRag",
                            "label": "Delete Knowledge RAG",
                        },
                        {
                            "action": "insertUpdateDataView",
                            "label": "Insert Update Data View",
                        },
                        {"action": "deleteDataView", "label": "Delete Data View"},
                    ],
                    "type": "RequestResponse",
                    "support_methods": ["POST"],
                    "is_auth_required": False,
                    "is_graphql": True,
                    "settings": "beta_core_openai",
                    "disabled_in_resources": True,  # Ignore adding to resource list.
                },
            },
        }
    ]


class AIKnowledgeEngine(SilvaEngineDynamoDBBase):
    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]) -> None:
        handlers_init(logger, **setting)

        self.logger = logger
        self.setting = setting

        SilvaEngineDynamoDBBase.__init__(self, logger, **setting)

    def ai_knowledge_graphql(self, **params: Dict[str, Any]) -> Any:
        schema = Schema(
            query=Query,
            mutation=Mutations,
            types=type_class(),
        )
        return self.graphql_execute(schema, **params)
