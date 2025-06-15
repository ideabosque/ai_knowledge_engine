import json
import traceback
import uuid
import pendulum
import logging
import humps
import re
from graphene import ResolveInfo
from silvaengine_utility import Utility
from typing import Any,  Dict, List
from .parser import Parser
from .config import Config
from .extractor import Extractor
from .operator import Operator


class S3DataProcessor:
    def __init__(self, setting: Dict[str, Any]):
        self.setting = setting
        self.structured_data = []
        self.unstructured_data = []
        self.entity_cache = []  # For staging entities, attributes, and relationships
        self.token_count = 0

    def process_file(
            self, 
            info: ResolveInfo, 
            document_source: str, 
            endpoint_id: str, 
            object_key: str, 
            skip_header: bool = True,
            position: int = 0,
            embedding_attributes: List[str] = [],
            graph_scheme_attributes: Dict[str, str] = {},
            vector_scheme_attributes: Dict[str, str] = {},
            max_retries: int = 3,
            editor: str = "",
            chunk_size_for_unstructured: int = 500,
            document_external_id: str = None,
        ):
        """
        Read S3 files line by line and process data
        """
        # TODO Parameters check
        # ! If the embedding_attributes / graph_scheme_attributes / vector_scheme_attributes empty, get default values from metadata to instead

        excute_start_time = pendulum.now("UTC")
        parser = Parser()
        extractor = Extractor(document_source=document_source, attributes=graph_scheme_attributes)
        operator = Operator(
            document_source=document_source, 
            endpoint_id=endpoint_id, 
            graph_scheme_attributes=graph_scheme_attributes,
            vector_scheme_attributes=vector_scheme_attributes,
            embedding_attributes=embedding_attributes,
        )
        document_title = f"Processed Document <{object_key}>"
        response = Config.aws_s3.get_object(Bucket=Config.aws_s3_bucket, Key=object_key, Range=f"bytes={position}-")
        stream = response['Body']
        chunk_index = 0
        header = ""
        chunk = ""
        i = 0

        if document_external_id is None:
            document_external_id = uuid.uuid4().hex

        try:
            for line in stream.iter_lines():
                try:
                    # Invoke self if the excute time is greater than 5 minutes
                    if pendulum.now("UTC") - excute_start_time > pendulum.duration(minutes=5):
                        self.invoke_self(
                            info=info,
                            document_source=document_source,
                            endpoint_id=endpoint_id,
                            object_key=object_key,
                            skip_header=True,
                            position = position,
                            embedding_attributes= embedding_attributes,
                            graph_scheme_attributes = graph_scheme_attributes,
                            vector_scheme_attributes = vector_scheme_attributes,
                            max_retries = max_retries,
                            editor = editor,
                            chunk_size_for_unstructured = chunk_size_for_unstructured,
                            document_external_id = document_external_id,
                        )
                        return

                    position += len(line) # Locates the location of the currently processed file and continues from this location only if an error occurs in file reading

                    if line.decode('utf-8').strip() == "":
                        continue
                    elif skip_header and i == 0:
                            header = line.decode('utf-8').strip()
                            i+=1
                            continue
                    i += 1
                    if i==2:
                        continue
                    print(f"\n*** LINE NUMBER: {i} ***************************************************\n\n\n")
                    data = line.decode('utf-8').strip()
                    # print(f"\n----------------header: {header} \n------data: {data}")
                    obj = parser.parse(header, data)

                    if type(obj) is dict and len(obj) > 0:
                        document_uuid = uuid.uuid4().hex
                        obj = {k: v for k, v in obj.items() if v}
                        entities = extractor.extract_entities(json.dumps(obj))
                        print("\n----------------extract_entities start: ")
                        print(entities)
                        print("\n----------------extract_entities end: ")
                        if not entities or type(entities) is not dict or not entities.get('entities'):
                            continue
                        embedding = operator.embedding(obj=obj)
                        print(f"\n vector dim length: ", len(embedding))
                        if not embedding:
                            continue
                        # 1. Write data to vector database
                        operator.save_vector_document(obj, document_uuid, embedding)
                        # 2. Save data to dynamodb
                        operator.save_document_chuck(
                            raw=data,
                            document_uuid=document_uuid,
                            document_title=document_title,
                            document_external_id=document_external_id,
                            embeddings=embedding,
                            editor=editor,
                            max_retries=max_retries,
                        )
                        # 3. Extract entities & write entitis to graph database
                        operator.save_graph_document(entities)

                    elif parser.need_read_next: # If the object is uncompletion, read the next line
                        continue

                    else: # Unstructured data
                        chunk += data
                        # tokens = extractor.tokenize_text(data)
                        tokens = len(re.findall(r'\b[\w\'-]+\b', data))

                        if type(tokens) is list:
                            self.token_count += len(tokens)

                        # Once per 1000 tokens
                        if self.token_count >= chunk_size_for_unstructured:
                            print(f"\n----------------chunk : \n{chunk} -----------\n")
                            # 1. Extract entities from the chunk
                            entities = extractor.extract_entities(extractor.clean_data(chunk))
                            print("\n----------------extract_entities start: ")
                            print(entities)
                            print("\n----------------extract_entities end: ")
                            if type(entities) is not dict or not entities.get('entities'):
                                continue
                            # 2. Save entities to the graph database
                            operator.save_graph_document(entities)
                            for entity in entities.get('entities'):
                                document_uuid = uuid.uuid4().hex
                                # 3. Convert the entities to embeddings
                                embedding = operator.embedding(obj=entity)
                                # 4. Save the embeddings to the vector database
                                operator.save_vector_document(entity, document_uuid, embedding)
                                # 5. Save the document chunk to dynamodb
                                operator.save_document_chuck(
                                    raw=chunk,
                                    document_uuid=document_uuid,
                                    document_title=document_title,
                                    document_external_id=document_external_id,
                                    embeddings=embedding,
                                    editor=editor,
                                    max_retries=max_retries,
                                )
                            self.token_count = 0
                            chunk_index += 1
                            chunk = ""
                except Exception as e:
                    print(traceback.format_exc())
                    continue

            # process last chunk
            if chunk:
                try:
                    print(f"\n----------------chunk : \n{chunk} -----------\n")
                    # 1. Extract entities from the chunk
                    entities = extractor.extract_entities(extractor.clean_data(chunk))
                    print("\n----------------extract_entities start: ")
                    print(entities)
                    print("\n----------------extract_entities end: ")
                    if type(entities) is dict or entities.get('entities'):
                        # 2. Save entities to the graph database
                        operator.save_graph_document(entities)
                        for entity in entities.get('entities'):
                            document_uuid = uuid.uuid4().hex
                            # 3. Convert the entities to embeddings
                            embedding = operator.embedding(obj=entity)
                            # 4. Save the embeddings to the vector database
                            operator.save_vector_document(entity, document_uuid, embedding)
                            # 5. Save the document chunk to dynamodb
                            operator.save_document_chuck(
                                raw=chunk,
                                document_uuid=document_uuid,
                                document_title=document_title,
                                document_external_id=document_external_id,
                                embeddings=embedding,
                                editor=editor,
                                max_retries=max_retries,
                            )
                except Exception as e:
                    print(traceback.format_exc())
        except Exception as e:
            # response = Config.aws_s3.get_object(Bucket=Config.aws_s3_bucket, Key=object_key, Range=f"bytes={position}-")
            # stream = response['Body']
            print(f"Skip: {e}")
            pass


    def invoke_self(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
        """
        Invoke Lambda function
        """
        return Utility.execute_graphql_query(
            logger=info.context.get("logger"),
            endpoint_id=info.context.get("endpoint_id"),
            funct="ai_knowledge_graphql",
            query=Utility.generate_graphql_operation("loadDocument", "Mutation", Config.graphql_schemes.get("ai_knowledge_graphql",{})),
            variables=humps.camelize(kwargs),
            setting=info.context.get("setting"),
            connection_id=None,
            test_mode=Config.test_mode,
            aws_lambda=Config.aws_lambda,
        )
