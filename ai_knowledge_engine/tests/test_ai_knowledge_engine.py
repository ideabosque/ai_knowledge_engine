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
    "module_bucket_name": os.getenv("ADAPTOR_BUCKET_NAME"),
    "module_zip_path": os.getenv("ADAPTOR_ZIP_PATH"),
    "module_extract_path": os.getenv("ADAPTOR_EXTRACT_PATH"),
    "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL"),
    "graph_db_connector_config": {
        "module_name": "neo4j_graph_connector",
        "class_name": "Neo4jConnector",
        "setting": {
            "neo4j_uri": os.getenv("NEO4J_URI"),
            "neo4j_username": os.getenv("NEO4J_USERNAME"),
            "neo4j_password": os.getenv("NEO4J_PASSWORD"),
            "neo4j_database": os.getenv("NEO4J_DATABASE"),
        },
    },
    "import_document_endpoint_id": os.getenv("IMPORT_DOCUMENT_ENDPOINT_ID"),
    "import_document_api_key": os.getenv("IMPORT_DOCUMENT_API_KEY"),
    "vector_db_connector_config": {
        "module_name": "redis_stack_connector",
        "class_name": "RedisStackConnector",
        "setting": {
            "REDIS_HOST": os.getenv("REDIS_HOST"),
            "REDIS_PORT": os.getenv("REDIS_PORT"),
            "REDIS_PASSWORD": os.getenv("REDIS_PASSWORD"),
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
                },
                "openai:company_data": {
                    "k": "100",
                    "return_fields": [
                        "id",
                        "name",
                        "detailed_description",
                        "vector_score",
                    ],
                    "vector_field": "content_vector",
                },
            },
        },
    },
    ""
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
   - Avoid Strict Relationship Chaining:
        Use separate `MATCH` clauses for flexibility:
        MATCH (o:Opportunity {deal_stage: "Lost"})-[:HANDLED_BY]->(sa:SalesAgent {name: "Moses Frase"})
        MATCH (o)-[:INVOLVES]->(a:Account)
        RETURN ...
   - Enhance Readability with Aliases:
        Example:
        RETURN o.id AS opportunity_id, a.name AS account_name
   - Output Requirements:  
       * The query must be formatted as a single-line plain text string without any markdown syntax (e.g., avoid using ```cypher```).  
       * Aliases Required: All nodes and relationships must include aliases, and every term in the RETURN clause must use `AS` to assign an alias (e.g., `RETURN p.name AS name, p.discount_price AS discount_price`).  
       * No Line Breaks: The query should not contain line breaks (e.g., "\n") and must exclude any additional explanations or formatting.  
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
c. Graph Schema Check: If the query can be addressed directly by the graph schema without similarity-based computations, return false. The following scenarios illustrate cases where Graph RAG is better suited than Vector Search. In such cases, Graph RAG should handle the query, and the system must return false as similarity-based computations are unnecessary:
- Complex Relationship Queries:
  Question: "What are the direct and indirect connections between Person A and Person B within a social network?"
  Explanation: Graph RAG can traverse the graph to uncover all possible paths and relationships between nodes, providing a structured and authoritative view that Vector Search lacks due to its focus on similarity rather than explicit relationships.
- Hierarchical Data Queries:
  Question: "What is the organizational hierarchy from the CEO down to the entry-level employees in this company?"
  Explanation: Graph RAG excels at mapping hierarchical structures by identifying parent-child relationships and organizational levels, whereas Vector Search is optimized for identifying similarities rather than navigating structured hierarchies.
- Contextual Path Queries:
  Question: "What are the steps involved in the supply chain from raw material procurement to the final product delivery?"
  Explanation: Graph RAG is capable of tracing specific paths and dependencies within a supply chain graph, providing a comprehensive step-by-step breakdown. In contrast, Vector Search lacks the ability to understand and process sequential steps in a structured process.
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
        "generate_extract_keywords": """
1. Task
Please refer to the provided scheme to extract the corresponding field information and relationships. 

2. Scheme
Scheme strucature:
```scheme
{scheme}
```

3. Constraints  
- If the original document is structured data, it needs to be extracted by line or object-by-object traversal.
- Match entities in the scheme after analyzing and understanding the source content, and extract values based on the attributes of the matched entities.
- According to the relationship in the scheme, associate the extracted entities and generate the corresponding Neo4j Cypher insertion statement.

4. Return
Please the return the extracted data in the following format:
```json
[
    {{
        "node_label": "The type of entity in Scheme, which will be used for the node label of the neo4j graph database",
        "properties": {{
            "name": "The name of the entity in the hit scheme",
            ... OTHER PROPERTIES OF THE ENTITY IN THE HIT SCHEME ...
        }},
        "relationships": [
            {{
                "relationship_type": "The type of relationship in Scheme, which will be used for associate with other entities",
                "target": "Associated with relationship_type Entity"
            }}
            ... OTHER RELATIONSHIPS ...
        ],
    }}
    ... OTHER NODES ...
]
```
""",
    },
    "endpoint_id": os.getenv("ENDPOINT_ID"),
    "test_mode": os.getenv("TEST_MODE"),
    "swap_bucket_name": os.getenv("SWAP_BUCKET_NAME"),
    "default_scheme": {
        "entities": {
            "product": {"attributes": ["product name", "sku"]},
            "customer": {"attributes": ["customer name", "address", "email", "phone"]},
            "company": {
                "attributes": [
                    "Account Name",
                    "Sector",
                    "Location",
                    "Total Opportunities",
                    "Total Revenue",
                    "Average Revenue per Opportunity",
                    "Engagement Level",
                    "Key Insight",
                    "Detailed Description",
                ]
            },
            "order": {"attributes": ["company name", "location"]},
        },
        "rules": [
            "Entity `customer` is belong to entity `company`",
            "Entity `customer` purchased entity `prodcut`",
        ],
    },
}

sys.path.insert(0, f"{os.getenv('BASE_DIR')}/ai_knowledge_engine")
sys.path.insert(1, f"{os.getenv('BASE_DIR')}/silvaengine_dynamodb_base")
sys.path.insert(2, f"{os.getenv('BASE_DIR')}/silvaengine_utility")
sys.path.insert(3, f"{os.getenv('BASE_DIR')}/neo4j_graph_connector")
sys.path.insert(4, f"{os.getenv('BASE_DIR')}/redis_stack_connector")

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
                # "documentUuid": "18153728364751229423",
                "documentExternalId": "XXXXXXXXXXXXXXXXXXX",
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
                "documentUuid": "7825045519416431087",
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
                "documentUuid": "14919712776599638511",
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
                # "processTaskUuid": "5480720187243237871",
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
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "processTaskUuid": "12927086442199388655",
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
                "processTaskUuid": "8234229927039275503",
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
                "processTaskUuid": "5480720187243237871",
                # "documentEntityUuid": "3779819455720853999",
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
                "processTaskUuid": "5480720187243237871",
                "documentEntityUuid": "5787719111019729391",
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
                "processTaskUuid": "5480720187243237871",
                "documentEntityUuid": "1783770419515560431",
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
                "processTaskUuid": "5480720187243237871",
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
                # "documentSource": "XXXXXXXXXXXXXXXXXXX",
                # # "metadataVersionUuid": "16622104501141246447",
                # "structuredDataViews": [],
                # "updatedBy": "XXXXXXXXXXXXXXXXXXX",
                "documentSource": "jack_test_2",
                "metadataVersionUuid": "5430499242157412847",
                "status": True,
                "updatedBy": "admin",
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
                "documentSource": "XXXXXXXXXXXXXXXXXXX",
                "metadataVersionUuid": "7472154973263434223",
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
                "metadataVersionUuid": "17589703106240385519",
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
                "documentSource": "jack_test_2",
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
                "dataSourceName": "XXXXXXXXXXXXXXXXXXX",
                "dataSourceType": "XXXXXXXXXXXXXXXXXXX",
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
                "dataSourceName": "jack_test_2",
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
                # "requestUuid": "8345496796697989615",
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
                "requestUuid": "16951530481417589231",
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
                "requestUuid": "4705164795813106159",
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

    # @unittest.skip("demonstrating skipping")
    def test_graphql_knowledge_rag(self):
        query = Utility.generate_graphql_operation("knowledgeRag", "Query", self.schema)
        logger.info(f"Query: {query}")
        payload = {
            "query": query,
            "variables": {
                # "userQuery": """Which product has the highest discounted price in the "High" price range?""",
                # "userQuery": """Find products with the same price range and rating group as "Daikin 1.5 Ton 5 Star Inverter Split AC (Copper, PM 2.5 Filter, 2022 Model, MTKM50U, White)".""",
                # "userQuery": """Recommend products similar to "Daikin 1.5 Ton 5 Star Inverter Split AC (Copper, PM 2.5 Filter, 2022 Model, MTKM50U, White)".""",
                # "userQuery": """Get all lost opportunities with account detail handled by Moses Frase.""",
                "userQuery": """Find companies relate to 'GTX Plus Basic'.""",
                "documentSource": "company_data",
                # "isSimilaritySearch": False,
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

    @unittest.skip("demonstrating skipping")
    def test_load_document(self):
        try:
            payload = {
                "query": """mutation loadDocument(
                    $documentSource: String!
                    $documentType: String!
                    $objectKey: String!
                ) {
                    loadDocument (
                        documentSource: $documentSource
                        documentType: $documentType
                        objectKey: $objectKey
                    ) {
                        ok
                    }
                }""",
                "variables": {
                    "documentSource": "load_test",
                    "documentType": "md",
                    "objectKey": "companies/cleaning-stuff-products.csv",
                },
            }
            response = self.ai_knowledge_engine.ai_knowledge_graphql(**payload)
            logger.info(response)
        except Exception as e:
            print(f"Error reading file: {e}")


if __name__ == "__main__":
    unittest.main()
