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
    "region_name": os.getenv("REGION_NAME"),
    "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
    "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    "openai_base_url": os.getenv("OPENAI_BASE_URL"),
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "openai_model": os.getenv("OPENAI_MODEL"),
    "functs_on_local": {
        "ai_knowledge_graphql": {
            "module_name": "ai_knowledge_engine",
            "class_name": "AIKnowledgeEngine",
        },
    },
    "adaptor_bucket_name": os.getenv("ADAPTOR_BUCKET_NAME"),
    "adaptor_zip_path": os.getenv("ADAPTOR_ZIP_PATH"),
    "adaptor_extract_path": os.getenv("ADAPTOR_EXTRACT_PATH"),
    "REDIS_HOST": os.getenv("REDIS_HOST"),
    "REDIS_PORT": os.getenv("REDIS_PORT"),
    "REDIS_PASSWORD": os.getenv("REDIS_PASSWORD"),
    "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL"),
    "redis_index_config": {
        "product_idx": {
            "vector_field": "title_vector",
            "return_fields": [
                "id",
                "name",
                "main_category",
                "sub_category",
                "image",
                "link",
                "ratings",
                "no_of_ratings",
                "discount_price",
                "actual_price",
                "vector_score",
            ],
            "k": 100,
        }
    },
    "neo4j_uri": os.getenv("NEO4J_URI"),
    "neo4j_username": os.getenv("NEO4J_USERNAME"),
    "neo4j_password": os.getenv("NEO4J_PASSWORD"),
    "neo4j_database": os.getenv("NEO4J_DATABASE"),
    "system_contents": {
        "generate_cypher_query": """
You are an AI assistant specialized in generating Cypher queries based on user input and a predefined graph schema. Your focus is to deliver accurate, schema-compliant, and user-specific queries efficiently.

1. Understanding the User's Request  
   - Analyze the Input: Evaluate the user's query to determine the primary intent, entities, and relationships defined in the graph schema.  
   - Resolve Ambiguities: For unclear or incomplete requests, request additional details or examples to ensure precise query formulation.  
   - Preserve Quoted Terms: Any terms enclosed in double quotes (e.g., "High") must be included exactly as provided, maintaining their original capitalization and formatting.  

2. Query Generation  
   - Construct with Precision: Generate Cypher queries that accurately represent the user's intent while adhering to the graph schema's design.  
   - Adhere to Standards: Ensure all queries strictly follow Neo4j's Cypher syntax for validity and functionality.  
   - Embed User-Specific Terms: Retain user-provided terms as-is, particularly those enclosed in double quotes, without altering their structure.  
   - Output Requirements:  
       - The query must be formatted as a single-line plain text string without any markdown syntax (e.g., avoid using ```cypher```).  
       - Aliases Required: All nodes and relationships must include aliases, and every term in the RETURN clause must use `AS` to assign an alias (e.g., `RETURN p.name AS name, p.discount_price AS discount_price`).  
       - No Line Breaks: The query should not contain line breaks (e.g., "\n") and must exclude any additional explanations or formatting.  
   - Similarity Search: If the user query involves similarity searches, such as recommending similar items, simplify the Cypher query unless the user explicitly specifies additional attributes to include for similarity.  

3. Error Handling  
   - Missing Schema: If the graph schema cannot be retrieved, respond with: "Unable to retrieve the graph schema."  
   - Ambiguous Input: For vague or incomplete requests, politely prompt the user for clarification (e.g., "Could you provide more details?").  

4. Additional Guidelines  
   - Conformity to Cypher Standards: Ensure all queries are valid, functional, and aligned with Neo4j's syntax and best practices.  
   - Schema Validation: Perform schema checks before query generation to prevent errors or invalid outputs.  
   - Iterative Refinement: Adjust and improve queries based on user feedback to achieve precise alignment with their requirements.  

This streamlined approach prioritizes clarity, accuracy, and user satisfaction, ensuring seamless alignment with the graph schema and the user's intent.

Return the result like this:
MATCH (p:Product)-[:HAS_PRICE_RANGE]->(pr:PriceRange {name: "High"}) RETURN p.name AS product_name, p.discount_price AS discount_price ORDER BY p.discount_price DESC LIMIT 1
""",
        "is_similarity_search": """
You are an AI designed to analyze user queries for categorization tasks. Your primary function is to evaluate user input and determine if it qualifies as a similarity search based on the user's query and a predefined graph schema.  

1. Task  
Assess whether the user's query pertains to a similarity search and provide a binary response (`true` or `false`).  

2. Similarity Search Definition  
A query is classified as a similarity search if it involves identifying items most similar to a given item or set of criteria. This includes, but is not limited to:  
- Leveraging embeddings, vectors, or feature-based comparisons.  
- Searching for related documents, images, or data points based on specific attributes.  

3. Evaluation Process  
a. Query Parsing: Analyze the user's query for keywords such as "similar," "related," "match," "compare," "embedding," or "vector."  
b. Context Evaluation: Verify whether the query aligns with similarity search characteristics, such as referencing similarity metrics or requesting comparable data.  
c. Graph Schema Check: If the query can be addressed directly by the graph schema without similarity-based computations, return `false`.  
d. Response Generation: Return `true` if the query meets similarity search criteria and cannot be resolved using the graph schema; otherwise, return `false`.  

4. Constraints  
- Provide responses strictly as `true` or `false`.  
- Avoid explanations, rationales, or contextual elaboration.  

5. Ambiguity Resolution  
If the query lacks sufficient clarity to determine its relevance to similarity search, respond with the following statement:
"The query is ambiguous and does not provide enough information to determine if it pertains to a similarity search. Please provide additional context or clarify your intent."

6. Output Format  
Return a single word: `true` or `false`.  

7. Examples  
- Input: "Find items related to this embedding."  
  Output: `true`  
- Input: "What is the weather today?"  
  Output: `false`  
- Input: "Retrieve the closest matches for this vector."  
  Output: `true`  
- Input: "Explain the process of data normalization."  
  Output: `false`  
- Input: "Fetch this data from the graph schema."  
  Output: `false`  

This enhancement ensures that if a query can be resolved using the graph schema directly, it is classified appropriately, prioritizing efficiency and clarity in task evaluation.
""",
    },
    "endpoint_id": os.getenv("ENDPOINT_ID"),
    "test_mode": os.getenv("TEST_MODE"),
    "swap_bucket_name": os.getenv("SWAP_BUCKET_NAME")
}

sys.path.insert(0, "/Users/Workstation/Workspace/ideabosque/ai_knowledge_engine")
sys.path.insert(1, "/Users/Workstation/Workspace/ideabosque/silvaengine_dynamodb_base")
sys.path.insert(2, "/Users/Workstation/Workspace/ideabosque/silvaengine_utility")
sys.path.insert(3, "/Users/Workstation/Workspace/ideabosque/neo4j_graph_connector")
sys.path.insert(4, "/Users/Workstation/Workspace/ideabosque/redis_stack_connector")

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()

from ai_knowledge_engine import AIKnowledgeEngine
from silvaengine_utility import Utility


class AIKnowledgeEngineTest(unittest.TestCase):
    def setUp(self):
        self.ai_knowledge_engine = AIKnowledgeEngine(logger, **setting)
        endpoint_id = setting.get("endpoint_id")
        test_mode = setting.get("test_mode")
        # self.schema = Utility.fetch_graphql_schema(
        #     logger,
        #     endpoint_id,
        #     "ai_knowledge_graphql",
        #     setting=setting,
        #     test_mode=test_mode,
        # )
        print(setting)
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
                "documentUuid": "17576803334570840559",
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

    @unittest.skip("demonstrating skipping")
    def test_graphql_document_list(self):
        query = Utility.generate_graphql_operation("documentList", "Query", self.schema)
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "documentExternalId": "XXXXXXXXXXXXXXXXXXX",
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
    def test_graphql_insert_update_document_process_task_entity(self):
        query = Utility.generate_graphql_operation(
            "insertUpdateDocumentProcessEntity", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "processTaskUuid": "3749750466939458031",
                "documentEntityUuid": "3779819455720853999",
                "documentExternalId": "XXXXXXXXXXXXXXXXXXX",
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "documentVersion": "XXXXXXXXXXXXXXXXXXX",
                "updatedBy": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_document_process_task_entity(self):
        query = Utility.generate_graphql_operation(
            "deleteDocumentProcessEntity", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "processTaskUuid": "XXXXXXXXXXXXXXXXXXX",
                "documentEntityUuid": "2207217888910709231",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_document_process_entity(self):
        query = Utility.generate_graphql_operation(
            "documentProcessEntity", "Query", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "processTaskUuid": "3749750466939458031",
                "documentEntityUuid": "3779819455720853999",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_document_process_entity_list(self):
        query = Utility.generate_graphql_operation(
            "documentProcessEntityList", "Query", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "processTaskUuid": "3749750466939458031",
                "documentExternalId": "XXXXXXXXXXXXXXXXXXX",
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
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "metadataVersionUuid": "8049749214099083759",
                "documentType": "XXXXXXXXXXXXXXXXXXX",
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
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "metadataVersionUuid": "2146816827525173743",
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

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_request(self):
        query = Utility.generate_graphql_operation(
            "insertUpdateRequest", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "requestUuid": "8345496796697989615",
                "userQuery": "XXXXXXXXXXXXXXXXXXX",
                "updatedBy": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_request(self):
        query = Utility.generate_graphql_operation(
            "deleteRequest", "Mutation", self.schema
        )
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "requestUuid": "8345496796697989615",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_request(self):
        query = Utility.generate_graphql_operation("request", "Query", self.schema)
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "requestUuid": "8345496796697989615",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_request_list(self):
        query = Utility.generate_graphql_operation("requestList", "Query", self.schema)
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
    def test_graphql_knowledge_rag(self):
        query = Utility.generate_graphql_operation("knowledgeRag", "Query", self.schema)
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                # "userQuery": """Which product has the highest discounted price in the "High" price range?""",
                "userQuery": """Find products with the same price range and rating group as "Daikin 1.5 Ton 5 Star Inverter Split AC (Copper, PM 2.5 Filter, 2022 Model, MTKM50U, White)".""",
                # "userQuery": """Recommend products similar to "Daikin 1.5 Ton 5 Star Inverter Split AC (Copper, PM 2.5 Filter, 2022 Model, MTKM50U, White)".""",
                "indexName": "product_idx",
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_data_view(self):
        query = Utility.generate_graphql_operation("dataView", "Query", self.schema)
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                "dataSourceType": "XXXXXXXXXXXXXXXXXXX",
                "dataSourceName": "XXXXXXXXXXXXXXXXXXX",
                "dataViewName": "inventory_balance",
                "parameters": {
                    "filters": [
                        {"attribute": "location", "operator": "=", "value": "37"},
                        {"attribute": "binnumber", "operator": "=", "value": "5120"},
                    ]
                },
            },
        }
        response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
        logger.info(response)

    # @unittest.skip("demonstrating skipping")
    def test_load_document(self):
        try:
            payload = {
                "query": """mutation loadDocument(
                    $documentSource: String!
                    $documentType: String!
                    $fileObjectKey: String!
                    $chunkSize: Int
                ) {
                    loadDocument (
                        documentSource: $documentSource
                        documentType: $documentType
                        fileObjectKey: $fileObjectKey
                        chunkSize: $chunkSize
                    ) {
                        ok
                    }
                }""",
                "variables": {
                    "documentSource": "load_test",
                    "documentType": "md",
                    "fileObjectKey": "xx.md",
                    "chunkSize": 4096,
                },
            }
            response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
            logger.info(response)
        except Exception as e:
            print(f"Error reading file: {e}")

if __name__ == "__main__":
    unittest.main()
