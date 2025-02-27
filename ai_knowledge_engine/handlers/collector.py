import json
import traceback
import uuid
import pendulum
import logging
from graphene import ResolveInfo
from silvaengine_utility import Utility
from typing import Any,  Dict, List
from .parser import Parser
from .initializer import Initializer
from .extractor import Extractor
from .operator import Operator


class S3DataProcessor:
    def __init__(self, setting: Dict[str, Any]):
        self.setting = setting
        self.structured_data = []
        self.unstructured_data = []
        self.entity_cache = []  # For staging entities, attributes, and relationships
        self.token_count = 0
        self.config = Initializer(setting=setting)

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
        ):
        """
        Read S3 files line by line and process data
        """
        excute_start_time = pendulum.now("UTC")
        parser = Parser()
        extractor = Extractor(self.config, document_source=document_source, attributes=graph_scheme_attributes)
        operator = Operator(
            self.config, 
            document_source=document_source, 
            endpoint_id=endpoint_id, 
            graph_scheme_attributes=graph_scheme_attributes,
            vector_scheme_attributes=vector_scheme_attributes,
            embedding_attributes=embedding_attributes,
        )
        document_external_id = uuid.uuid4().hex
        document_title = f"Processed Document <{self.config}>"
        response = self.config.aws_s3.get_object(Bucket=self.config.aws_s3_bucket, Key=object_key, Range=f"bytes={position}-")
        stream = response['Body']
        chunk_index = 0
        header = ""
        chunk = ""
        i = 0

        try:
            for line in stream.iter_lines():
                try:
                    # Invoke self if the excute time is greater than 10 minutes
                    if pendulum.now("UTC") - excute_start_time > pendulum.duration(minutes=10):
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
                    print(f"\n*** LINE NUMBER: {i} ***************************************************\n\n\n")
                    data = line.decode('utf-8').strip()
                    obj = parser.parse(header, data)

                    if type(obj) is dict and len(obj) > 0:
                        document_uuid = uuid.uuid4().hex
                        embedding = operator.embedding(obj=obj)
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
                        operator.save_graph_document(extractor.extract_entities(json.dumps(obj)))

                    elif parser.need_read_next: # If the object is uncompletion, read the next line
                        continue

                    else: # Unstructured data
                        chunk += data
                        tokens = extractor.tokenize_text(data)

                        if type(tokens) is list:
                            self.token_count += len(tokens)


                        # Once per 1000 tokens
                        if self.token_count >= chunk_size_for_unstructured:
                            # 1. Extract entities from the chunk
                            entities = extractor.extract_entities(extractor.clean_data(chunk))
                            # 2. Save entities to the graph database
                            operator.save_graph_document(entities)
                            document_uuid = uuid.uuid4().hex
                            # 3. Convert the entities to embeddings
                            embedding = operator.embedding(obj=entities)
                            # 4. Save the embeddings to the vector database
                            operator.save_vector_document(obj, document_uuid, embedding)
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
                except Exception as e:
                    print(traceback.format_exc())
                    continue
        except Exception as e:
            response = self.config.aws_s3.get_object(Bucket=self.config.aws_s3_bucket, Key=object_key, Range=f"bytes={position}-")
            stream = response['Body']
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
            query=Utility.generate_graphql_operation("loadDocument", "Mutation", self.config.graphql_schemes),
            variables=kwargs,
            setting=info.context.get("setting"),
            connection_id=None,
            test_mode=None,
            aws_lambda=self.config.aws_lambda,
        )
