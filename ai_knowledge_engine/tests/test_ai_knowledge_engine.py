#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import json
import logging
import os
import sys
import time
import unittest
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
setting = {
    "region_name": os.getenv("region_name"),
    "aws_access_key_id": os.getenv("aws_access_key_id"),
    "aws_secret_access_key": os.getenv("aws_secret_access_key"),
    "functs_on_local": {
        "ai_knowledge_graphql": {
            "module_name": "ai_knowledge_engine",
            "class_name": "AIKnowledgeEngine",
        },
    },
    "endpoint_id": os.getenv("endpoint_id"),
    "test_mode": os.getenv("test_mode"),
}

sys.path.insert(0, "C:/Users/bibo7/gitrepo/silvaengine/ai_knowledge_engine")
sys.path.insert(1, "C:/Users/bibo7/gitrepo/silvaengine/silvaengine_dynamodb_base")
sys.path.insert(2, "C:/Users/bibo7/gitrepo/silvaengine/silvaengine_utility")

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()

from ai_knowledge_engine import AIKnowledgeEngine
from silvaengine_utility import Utility


class AIKnowledgeEngineTest(unittest.TestCase):
    def setUp(self):
        self.ai_knowledge_engine = AIKnowledgeEngine(logger, **setting)
        endpoint_id = setting.get("endpoint_id")
        test_mode = setting.get("test_mode")
        self.schema = Utility.fetch_graphql_schema(
            logger,
            endpoint_id,
            "ai_knowledge_graphql",
            setting=setting,
            test_mode=test_mode,
        )
        logger.info("Initiate AIKnowledgeEngineTest ...")

    def tearDown(self):
        logger.info("Destory AIKnowledgeEngineTest ...")

    @unittest.skip("demonstrating skipping")
    def test_graphql_ping(self):
        query = Utility.generate_graphql_operation("ping", "Query", self.schema)
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {},
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_document(self):
        query = Utility.generate_graphql_operation(
            "insertUpdateDocument", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "documentUuid": "8073934999525134831",
                "documentExternalId": "XXXXXXXXXXXXXXXXXXX",
                "documentType": "XXXXXXXXXXXXXXXXXXX",
                "documentTitle": "XXXXXXXXXXXXXXXXXXX",
                "documentContent": "XXXXXXXXXXXXXXXXXXX",
                "updatedBy": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_document(self):
        query = Utility.generate_graphql_operation(
            "deleteDocument", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "documentUuid": "8073934999525134831",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_document(self):
        query = Utility.generate_graphql_operation("document", "Query", self.schema)
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "documentUuid": "8073934999525134831",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    # @unittest.skip("demonstrating skipping")
    def test_graphql_document_list(self):
        query = Utility.generate_graphql_operation("documentList", "Query", self.schema)
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_document_source(self):
        query = Utility.generate_graphql_operation(
            "insertUpdateDocumentSource", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentType": "XXXXXXXXXXXXXXXXXXX",
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "moduleName": "XXXXXXXXXXXXXXXXXXX",
                "className": "XXXXXXXXXXXXXXXXXXX",
                "configuration": {},
                "updatedBy": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_document_source(self):
        query = Utility.generate_graphql_operation(
            "deleteDocumentSource", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentType": "XXXXXXXXXXXXXXXXXXX",
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_document_source(self):
        query = Utility.generate_graphql_operation(
            "documentSource", "Query", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentType": "XXXXXXXXXXXXXXXXXXX",
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_document_source_list(self):
        query = Utility.generate_graphql_operation(
            "documentSourceList", "Query", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentType": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_document_process_task(self):
        query = Utility.generate_graphql_operation(
            "insertUpdateDocumentProcessTask", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "processTaskUuid": "3749750466939458031",
                "documentType": "XXXXXXXXXXXXXXXXXXX",
                "entities": [],
                "startTime": "2024-12-24T05:30:08.827734+0000",
                "updatedBy": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_document_process_task(self):
        query = Utility.generate_graphql_operation(
            "deleteDocumentProcessTask", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentType": "XXXXXXXXXXXXXXXXXXX",
                "processTaskUuid": "6153210523639681519",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_document_process_task(self):
        query = Utility.generate_graphql_operation(
            "documentProcessTask", "Query", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "processTaskUuid": "3749750466939458031",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_document_process_task_list(self):
        query = Utility.generate_graphql_operation(
            "documentProcessTaskList", "Query", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_knowledge_graph_metadata(self):
        query = Utility.generate_graphql_operation(
            "insertUpdateKnowledgeGraphMetadata", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentType": "XXXXXXXXXXXXXXXXXXX",
                "metadataVersionUuid": "4261954170568774127",
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "dataSourceName": "XXXXXXXXXXXXXXXXXXX",
                "dataSourceType": "XXXXXXXXXXXXXXXXXXX",
                "dataViewName": "XXXXXXXXXXXXXXXXXXX",
                "updatedBy": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_knowledge_graph_metadata(self):
        query = Utility.generate_graphql_operation(
            "deleteKnowledgeGraphMetadata", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentType": "XXXXXXXXXXXXXXXXXXX",
                "metadataVersionUuid": "16934475745462194671",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_knowledge_graph_metadata(self):
        query = Utility.generate_graphql_operation(
            "knowledgeGraphMetadata", "Query", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentType": "XXXXXXXXXXXXXXXXXXX",
                "metadataVersionUuid": "4261954170568774127",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_knowledge_graph_metadata_list(self):
        query = Utility.generate_graphql_operation(
            "knowledgeGraphMetadataList", "Query", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentType": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_data_source(self):
        query = Utility.generate_graphql_operation(
            "insertUpdateDataSource", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "dataSourceType": "XXXXXXXXXXXXXXXXXXX",
                "dataSourceName": "XXXXXXXXXXXXXXXXXXX",
                "moduleName": "XXXXXXXXXXXXXXXXXXXX",
                "className": "XXXXXXXXXXXXXXXXXXX",
                "configuration": {},
                "updatedBy": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_data_source(self):
        query = Utility.generate_graphql_operation(
            "deleteDataSource", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "dataSourceType": "XXXXXXXXXXXXXXXXXXX",
                "dataSourceName": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_data_source(self):
        query = Utility.generate_graphql_operation("dataSource", "Query", self.schema)
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "dataSourceType": "XXXXXXXXXXXXXXXXXXX",
                "dataSourceName": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_data_source_list(self):
        query = Utility.generate_graphql_operation(
            "dataSourceList", "Query", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "dataSourceType": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)


if __name__ == "__main__":
    unittest.main()
