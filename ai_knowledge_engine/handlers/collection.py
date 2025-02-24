import boto3
import json
import re
import logging
import os
import sys
import traceback
import zipfile
import uuid
import pendulum
import csv
import xmltodict
import yaml
import toml
import time
from io import StringIO
from xml.etree import ElementTree as ET
from typing import List, Dict, Any
from openai import OpenAI
from graphene import ResolveInfo
from silvaengine_utility import Utility
from silvaengine_base import LambdaBase
from typing import Any, Callable, Dict, List, Optional, Tuple
from ..models import DocumentModel


class S3DataProcessor:
    def __init__(self, setting: Dict[str, Any]):
        self.setting = setting
        self.structured_data = []
        self.unstructured_data = []
        self.entity_cache = []  # For staging entities, attributes, and relationships
        self.token_count = 0

        if "EMBEDDING_MODEL" in setting:
            self.embedding_model = setting["EMBEDDING_MODEL"]
        if "openai_model" in setting:
            self.openai_model = setting["openai_model"]
        if "system_contents" in setting:
            self.system_contents = setting["system_contents"]

        self._setup_function_paths()
        self._initialize_aws_services()
        self._initialize_openai_client()
        self._initialize_graph_database()
        self._initialize_vector_database()

    def _initialize_aws_services(self) -> None:
        """
        Initialize AWS services
        """
        if all(
            self.setting.get(k)
            for k in ["region_name", "aws_access_key_id", "aws_secret_access_key"]
        ):
            aws_credentials = {
                "region_name": self.setting["region_name"],
                "aws_access_key_id": self.setting["aws_access_key_id"],
                "aws_secret_access_key": self.setting["aws_secret_access_key"],
            }
        else:
            aws_credentials = {}

        self.aws_s3_bucket = self.setting.get("swap_bucket_name")
        self.aws_s3 = boto3.client("s3", **aws_credentials)

    def _initialize_openai_client(self) -> None:
        """
        Initialize OpenAI client
        """
        if "openai_api_key" in self.setting:
            openai_setting = {"api_key": self.setting["openai_api_key"]}
            if "openai_base_url" in self.setting:
                openai_setting.update({"base_url": self.setting["openai_base_url"]})
            self.openai_client = OpenAI(**openai_setting)

    def _initialize_graph_database(self, logger: logging.Logger = None) -> None:
        """
        Initialize graph database
        """
        if "graph_db_connector_config" in self.setting:
            self.graph_db_connector = self._get_class_object(
                logger,
                self.setting["graph_db_connector_config"]["module_name"],
                self.setting["graph_db_connector_config"]["class_name"],
                **self.setting["graph_db_connector_config"]["setting"],
            )
            self.graph_schema = self.graph_db_connector.get_graph_schema()

    def _initialize_vector_database(self, logger: logging.Logger = None) -> None:
        """
        Initialize vector database
        """
        if "vector_db_connector_config" in self.setting:
            self.vector_db_connector = self._get_class_object(
                logger,
                self.setting["vector_db_connector_config"]["module_name"],
                self.setting["vector_db_connector_config"]["class_name"],
                **dict(
                    self.setting["vector_db_connector_config"]["setting"],
                    **{
                        "openai_api_key": self.setting["openai_api_key"],
                        "EMBEDDING_MODEL": self.embedding_model,
                    },
                ),
            )

    def _get_class_object(self, logger: logging.Logger, module_name: str, class_name: str, **setting: Dict[str, Any]) -> Optional[Callable]:
        """
        Get class object
        """
        try:
            if not self._module_exists(logger, module_name):
                # Download and extract the module if it doesn't exist
                self._download_and_extract_module(logger, module_name)
            # Add the extracted module to sys.path
            module_path = f"{self.module_extract_path}/{module_name}"
            if module_path not in sys.path:
                sys.path.append(module_path)
            _class = getattr(__import__(module_name), class_name)
            return _class(
                logger,
                **Utility.json_loads(Utility.json_dumps(setting)),
            )
        except Exception as e:
            log = traceback.format_exc()
            if logger:
                logger.error(log)
            raise e

    def _setup_function_paths(self) -> None:
        """
        Set up function paths
        """
        self.module_bucket_name = self.setting.get("module_bucket_name")
        self.module_zip_path = self.setting.get("module_zip_path", "/tmp/adaptor_zips")
        self.module_extract_path = self.setting.get("module_extract_path", "/tmp/adaptors")
        os.makedirs(self.module_zip_path, exist_ok=True)
        os.makedirs(self.module_extract_path, exist_ok=True)

    def _module_exists(self, logger: logging.Logger, module_name: str) -> bool:
        """
        Check if the module exists in the specified path.
        """
        module_dir = os.path.join(self.module_extract_path, module_name)
        if os.path.exists(module_dir) and os.path.isdir(module_dir):
            if logger:
                logger.info(f"Module {module_name} found in {self.module_extract_path}.")
            return True
        if logger:
            logger.info(f"Module {module_name} not found in {self.module_extract_path}.")
        return False

    def _download_and_extract_module(self, logger: logging.Logger, module_name: str) -> None:
        """
        Download and extract the module from S3 if not already extracted.
        """
        key = f"{module_name}.zip"
        zip_path = f"{self.module_zip_path}/{key}"
        if logger:
            logger.info(f"Downloading module from S3: bucket={self.module_bucket_name}, key={key}")
        self.aws_s3.download_file(self.module_bucket_name, key, zip_path)
        if logger:
            logger.info(f"Downloaded {key} from S3 to {zip_path}")
        # Extract the ZIP file
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(self.module_extract_path)
        if logger:
            logger.info(f"Extracted module to {self.module_extract_path}")

    def _clean_data(self, line: str) -> str:
        """
        Data cleaning to remove noisy information
        """
        return re.sub(r'\s+', ' ', line).strip()

    def _extract_entities_from_structured(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extracting entities, attributes, and relationships from structured data
        """
        entities = []
        for key, value in data.items():
            entities.append({"entity": key, "attribute": value, "relation": "HAS_ATTRIBUTE"})
        return entities

    def _extract_entities_from_unstructured(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracting entities, attributes, and relationships from data for graph
        """
        system_prompt = """Please adhere to the following rules strictly:
1. Enter: One line of CSV data, which may contain the following fields:
- Personal information (name, age, occupation, etc.)
- Geographical location (city, country, etc.)
- Organizational information (company name, department, etc.)
- Product infomation (name, size, price, type, catelog, etc.)
- Order infomation (product name, qty, order owner, etc.)

2. Output requirements:
* Entity identification:
- Entity types that must be identified: Person/Location/Organization
- Entity Attributes: Extract relevant attributes (such as age, position, etc.) from the original data source
* Relationship Recognition:
- WORK_AT (work in)/LIVE_IN (live in)/BELONG_TO (belong to) and other semantic relationships
Output format (strictly JSON format):
{
    "entities": [
        {"id": 1, "type": "Person", "name": "John Doe", "properties": {"age":30}, ...},
        {"id": 2, "type": "Location", "name": "New York", ...},
        {"id": 3, "type": "Organization", "name": "Apple", ...}
        {"id": 4, "type": "Product", "name": "Apple", "type": "abc", ...}
        ...
    ],
    "relationships": [
        {"from": 1, "to": 3, "type": "WORK_AT", "properties": {"position":"Engineer"}},
        {"from": 1, "to": 2, "type": "LIVE_IN"}
        ...
    ]
}"""
        response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
        )

        try:
            entities = json.loads(response.choices[0].message.content)
            return entities
        except json.JSONDecodeError:
            return []

    def _tokenize_text(self, text: str) -> List[str]:
        """
        Segmentation of unstructured data using OpenAI
        """
        prompt = f"Please tokenize the following text: {text}. Return the tokens as a JSON array."
        response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {"role": "system", "content":prompt},
                {"role": "user", "content": text}
            ]
        )
        try:
            tokens = json.loads(response.choices[0].message.content)
            return tokens
        except json.JSONDecodeError:
            return []

    def _save_to_dynamodb(
        self,
        document_source: str,
        document_type: str,
        document_title: str,
        data: List[Dict[str, Any]],
        redis_index_name: str,
        is_structured_data: bool,
    ):
        """
        Store data in batches to DynamoDB
        """
        now = pendulum.now("UTC")
        document_uuid = uuid.uuid4().hex
        document_external_id = document_uuid
        chunk_index = 0

        max_retries = 5 
        retry_count = 0

        while retry_count < max_retries:
            try:
                with DocumentModel.batch_write() as batch:
                    for item in data:
                        if item.get("data") is not None:
                            print("\n\n>>>>>>>>>>> _save_to_dynamodb:\n", document_uuid, chunk_index)
                            
                            embeddings = self.openai_client.embeddings.create(
                                input=json.dumps(item.get("data")), model=self.embedding_model
                            )
                            title_embedding = embeddings.data[0].embedding
                            content_embedding = embeddings.data[0].embedding

                            self.vector_db_connector.index_document(
                                prefix=redis_index_name,
                                key="id",
                                doc={
                                    "id": document_uuid,
                                    "content_vector": content_embedding,
                                    "content": item.get("data"),
                                },
                            )

                            batch.save(DocumentModel(
                                document_source=document_source,
                                document_uuid=f"{document_uuid}",
                                document_external_id=f"{document_external_id}",
                                endpoint_id=document_type,
                                document_title=f"{document_title} ",
                                document_content=json.dumps(item.get("data")),
                                chunk_index=chunk_index,
                                title_embedding=title_embedding,
                                content_embedding=content_embedding,
                                created_at=now,
                                updated_at=now,
                                updated_by="load",
                            ))

                            document_uuid = uuid.uuid4().hex

                            if not is_structured_data:
                                chunk_index +=1
                break
            except Exception as e:
                retry_count += 1
                print(f"Error: {e}")
                print(f"Retrying... Attempt {retry_count}")
                time.sleep(2 ** retry_count)

    def _generate_neo4j_insert_statements(self, entities: List[Dict[str, Any]]) -> str:
        """
        Generate Neo4j insert statement
        """
        with self.graph_db_connector.driver.session(
            database=self.setting.get("neo4j_database", "neo4j")
        ) as session:
            for item in entities:
                try:
                    node_creations = []
                    relationship_creations = []
                    var_counter = 1
                    var_mapping = {}

                    if 'entities' in item:
                        for entity in item['entities']:
                            node_type = entity['type'].replace(" ", "_")
                            node_id = entity['id']
                            properties = []
                            for key, value in entity.items():
                                if key not in ['id', 'type']:
                                    if ' ' in key:
                                        key = f'`{key}`'
                                    if isinstance(value, str):
                                        value = value.replace('"', '\\"')
                                        properties.append(f'{key}: "{value}"')
                                    else:
                                        properties.append(f'{key}: {value}')
                            properties_str = ', '.join(properties)
                            var_name = f'n{var_counter}'
                            node_creations.append(f'({var_name}:{node_type} {{id: {node_id}, {properties_str}}})')
                            var_mapping[node_id] = var_name
                            var_counter += 1

                    if 'relationships' in item:
                        for relationship in item['relationships']:
                            from_id = relationship['from']
                            to_id = relationship['to']
                            rel_type = relationship['type']
                            from_var = var_mapping[from_id]
                            to_var = var_mapping[to_id]
                            relationship_creations.append(f'({from_var})-[:{rel_type}]->({to_var})')

                    if len(node_creations) < 1:
                        continue

                    cypher_query = f'CREATE {", ".join(node_creations)}'

                    if relationship_creations:
                        cypher_query += f', {", ".join(relationship_creations)}'

                    session.run(cypher_query)
                except:
                    print(f"Error in document pipeline: {traceback.format_exc()}")
                    pass


    def _write_to_neo4j(self, entities: List[Dict[str, Any]]):
        """
        Write entities, attributes, and relationships to Neo4j
        """
        self._generate_neo4j_insert_statements(entities)

        # if cypher_query != "":
        #      with self.graph_db_connector.driver.session(
        #         database=self.setting.get("neo4j_database", "neo4j")
        #     ) as session:
        #          session.run(cypher_query)

    def process_file(
            self, 
            info: ResolveInfo, 
            document_source: str, 
            document_type: str, 
            object_key: str, 
            include_header: bool = True,
            position: int = 0,
        ):
        """
        Read S3 files line by line and process data
        """
        document_title = f"Processed Document {pendulum.now().to_datetime_string()}"
        document_classifier= DocumentClassifier(
            aws_s3_client=self.aws_s3,
            aws_s3_bucket=self.aws_s3_bucket, 
            object_key=object_key,
        )
        is_structured_data = document_classifier.is_structured_document()
        response = self.aws_s3.get_object(Bucket=self.aws_s3_bucket, Key=object_key, Range=f"bytes={position}-")
        stream = response['Body']
        redis_index_name = f"{document_type}:{document_source}"
        header = None
        start_time = pendulum.now("UTC")
        i = 0

        self.vector_db_connector.create_redis_index(
            index_name=redis_index_name,
            fields={
                "id": "TEXT",
                "name": "TEXT",
                "content_vector": "VECTOR",
                "content": "TEXT",
            },
            prefix=redis_index_name,
        )

        try:
            for line in stream.iter_lines():
                line_length = len(line)

                if pendulum.now("UTC") - start_time > pendulum.duration(minutes=10):
                    return self.invoke_self(
                        info=info, 
                        document_source= document_source, 
                        document_type=document_type, 
                        object_key=object_key, 
                        include_header=False,
                        start_line=i,
                    )

                line = self._clean_data(line.decode('utf-8'))

                if is_structured_data:
                    if include_header and i == 0: 
                        header = line
                        i+=1
                        continue

                    entities = self._extract_entities_from_unstructured(header+"\n\n"+line)
                    self.structured_data.append({"data": line, "entities": entities})

                    if type(entities) is list or type(entities) is dict:
                        self.entity_cache.append(entities)

                    # Every 20 pieces of structured data are stored
                    if len(self.structured_data) >= 20:
                        self._save_to_dynamodb(
                            document_source=document_source,
                            document_type=document_type,
                            document_title=document_title,
                            data=self.structured_data,
                            redis_index_name=redis_index_name,
                            is_structured_data=True,
                        )
                        self._write_to_neo4j(self.entity_cache)
                        self.structured_data = []
                        self.entity_cache = []

                else:
                    # Processing unstructured data
                    entities = self._extract_entities_from_unstructured(line)
                    tokens = self._tokenize_text(line)
                    self.unstructured_data.append({"text": line, "tokens": tokens, "entities": entities})

                    if type(entities) is list:
                        self.entity_cache.extend(entities)

                    if type(tokens) is list:
                        self.token_count += len(tokens)

                    # Once per 1000 tokens
                    if self.token_count >= 1000:
                        self._save_to_dynamodb(
                            document_source=document_source,
                            document_type=document_type,
                            document_title=document_title,
                            data=self.unstructured_data,
                            redis_index_name=redis_index_name,
                            is_structured_data=False,
                        )
                        self._write_to_neo4j(self.entity_cache)
                        self.unstructured_data = []
                        self.entity_cache = []
                        self.token_count = 0

                i += 1
                position += line_length
        except Exception as e:
            print(f"Skip: {e}")
            response = self.aws_s3.get_object(Bucket=self.aws_s3_bucket, Key=object_key, Range=f'bytes={position}-')
            stream = response['Body']
            pass

        # Process the remaining data
        if self.structured_data:
            self._save_to_dynamodb(
                document_source=document_source,
                document_type=document_type,
                document_title=document_title,
                data=self.structured_data,
                redis_index_name=redis_index_name,
                is_structured_data=True,
            )
            self._write_to_neo4j(self.entity_cache)

        if self.unstructured_data:
            self._save_to_dynamodb(
                document_source=document_source,
                document_type=document_type,
                document_title=document_title,
                data=self.unstructured_data,
                redis_index_name=redis_index_name,
                is_structured_data=False,
            )
            self._write_to_neo4j(self.entity_cache)

    def invoke_self(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
        """
        Invoke Lambda function
        """
        method = "POST"
        (settings, function) = LambdaBase.get_function(
            endpoint_id=self.setting.get("import_document_endpoint_id"),
            funct="ai_knowledge_graphql",
            api_key=self.setting.get("import_document_api_key"),
            method=str(method).strip().upper(),
        )

        parameters = (
            parameters
            if Utility.is_json_string(kwargs)
            else Utility.json_dumps(kwargs)
        )
        context = (
            parameters
            if Utility.is_json_string(info.context)
            else Utility.json_dumps(info.context)
        )
        return LambdaBase.invoke(
            FunctionName=str(function.aws_lambda_arn).strip(),
            InvocationType="Event",
            Payload=json.dumps(
                {
                    "MODULENAME": "ai_knowledge_engine",
                    "CLASSNAME": "AIKnowledgeEngine",
                    "funct": "ai_knowledge_graphql",
                    "setting": Utility.json_dumps(self.setting),
                    "params": parameters,
                    "body": parameters,
                    "context": context,
                }
            ),
        )

class DocumentClassifier:
    def __init__(self, aws_s3_client: Any, aws_s3_bucket: str, object_key: str):
        self.structured_mime_types = {
            "application/json",
            "text/csv",
            "application/xml",
            "text/xml",
            "application/x-yaml",
            "application/x-parquet"
        }
        self.structured_extensions = {".json", ".csv", ".xml", ".yaml", ".parquet"}
        self.aws_s3_client = aws_s3_client
        self.aws_s3_bucket = aws_s3_bucket
        self.object_key = object_key
    def check_structured_by_mime(self) -> bool:
        """
        Determine whether it is structured by MIME type
        """
        response = self.aws_s3_client.head_object(Bucket=self.aws_s3_bucket, Key=self.object_key)
        mime_type = response.get('ContentType', 'application/octet-stream')
    
        return mime_type in self.structured_mime_types

    def check_structured_by_extension(self) -> bool:
        """
        Determine whether it is structured by file extension
        """
        _, ext = os.path.splitext(self.object_key)
        return ext.lower() in self.structured_extensions

    def check_structured_by_content(self) -> bool:
        """
        Determine whether it is structured by the content of the file
        """
        try:
            response = self.aws_s3_client.get_object(Bucket=self.aws_s3_bucket, Key=self.object_key)
            stream = response['Body']
            first_line = stream.readline().strip().decode('utf-8')
            
            if first_line.startswith(("{", "[")):
                try:
                    json.loads(first_line)
                    return True
                except json.JSONDecodeError:
                    pass

            if "," in first_line or ";" in first_line:
                try:
                    csv.Sniffer().sniff(first_line)
                    return True
                except csv.Error:
                    pass

            if first_line.startswith("<"):
                try:
                    ET.fromstring(first_line + "</root>") 
                    return True
                except ET.ParseError:
                    pass

            return False
        except UnicodeDecodeError:
            # Binary files (such as PDFs) are considered unstructured
            return False
        except Exception as e:
            return False

    def is_structured_document(self) -> bool:
        """
        Comprehensive judgment of document type
        """
         # 1. Judging by file extension
        if self.check_structured_by_extension():
            return True
        
        # 2. Judging by MIME type
        if self.check_structured_by_mime():
            return True
        
        # 3. Through content analysis
        if self.check_structured_by_content():
            return True
        
        return False

    def convert_to_json(self, data):
        """
        Transforming different types of structured data into JSON
        """    
        try:
            json_data = json.loads(data)
            return json.dumps(json_data, ensure_ascii=False, indent=4)
        except Exception as e:
            pass
        try:
            csv_file = StringIO(data)
            reader = csv.DictReader(csv_file)
            data_list = list(reader)
            return json.dumps(data_list, ensure_ascii=False, indent=4)
        except Exception as e:
            pass

        try:
            data_dict = xmltodict.parse(data)
            return json.dumps(data_dict, ensure_ascii=False, indent=4)
        except Exception as e:
            pass

        try:
            yaml_content = yaml.safe_load(data)
            return json.dumps(yaml_content, ensure_ascii=False, indent=4)
        except Exception as e:
            pass
        try:
            toml_content = toml.loads(data)
            return json.dumps(toml_content, ensure_ascii=False, indent=4)
        except Exception as e:
            pass

        return None




