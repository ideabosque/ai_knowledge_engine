
import json, pendulum, uuid, time
from typing import Any, Dict, List
from .config import Config
from ..models.document import DocumentModel

class Operator:
    def __init__(
            self,
            document_source: str,
            endpoint_id:str, 
            graph_scheme_attributes: Dict[str, str],
            vector_scheme_attributes: Dict[str, str],
            embedding_attributes: List[str] = [],
        ):
        self.document_source = document_source
        self.endpoint_id = endpoint_id
        self.graph_scheme_attributes = graph_scheme_attributes
        self.vector_scheme_attributes = vector_scheme_attributes
        self.embedding_attributes = embedding_attributes
        self.graph_attributes = list(graph_scheme_attributes.values())

        self._create_vector_database_index()

    def _generate_vector_database_index_name(self) -> str:
        """
        Build index name for vector database
        """
        return f"{self.endpoint_id}:{self.document_source}"


    def _generate_cypher_statments(self, data: Dict[str, Any]) -> str:
        """
        Generate Cypher statements for the given data.
        """
        try:
            cypher_statements = []

            for entity in data.get('entities', []):
                if "type" in entity:
                    node_type = entity['type']
                    properties = []
                    if entity.get('properties') and type(entity['properties']) is dict:
                        entity.update(entity.get('properties'))

                    for key, value in entity.items():
                        if key == 'type':
                            continue
                        elif key.lower() in self.graph_attributes:
                            if isinstance(value, str):
                                value = value.replace("'", "\\'")
                                properties.append(f"{key}: '{value}'")
                            else:
                                properties.append(f"{key}: {value}")

                    if len(properties) > 0:
                        statement = ", ".join(properties)
                        cypher_statements.append(f"(:{node_type} {{ {statement} }});")

            for relation in data.get('relations', []):
                print(f">>>>>>>>>>>>> relation:{relation}\n")

            if type(cypher_statements) is list and len(cypher_statements) > 0:
                return f"CREATE {', '.join(cypher_statements)}"
            
            return None
        except Exception as e:
            print(f"Error: {e}")
            raise e

    def _generate_cypher_upsert_statments(self, data: Dict[str, Any]) -> list:
        """
        Generate Cypher statements for the given data.
        """
        try:
            type_datas = {}
            for entity in data.get('entities', []):
                if "type" in entity:
                    node_type = entity['type']
                    properties = {}
                    if entity.get('properties') and type(entity['properties']) is dict:
                        entity.update(entity.get('properties'))

                    for key, value in entity.items():
                        if key == 'type':
                            continue
                        elif key.lower() in self.graph_attributes:
                            properties[key] = value.replace("'", "\\'") if isinstance(value, str) else value

                    if len(properties) > 0:
                        if node_type not in type_datas:
                            type_datas[node_type] = []
                        type_datas[node_type].append(properties)

            for relation in data.get('relations', []):
                print(f">>>>>>>>>>>>> relation:{relation}\n")

            if len(type_datas) > 0:
                cypher_statements = []
                for node_type, node_data in type_datas.items():
                    query = """
UNWIND $nodes AS node 
MERGE (n:%s {name: node.name}) 
ON CREATE SET n = node 
ON MATCH SET n += node
""" % (node_type)
                    cypher_statements.append({
                        "query": query,
                        "nodes": node_data
                    })
                return cypher_statements

            return None
        except Exception as e:
            print(f"Error: {e}")
            raise e

    def _create_vector_database_index(self):
        """
        Create vector database index
        """
        try:
            index_name = self._generate_vector_database_index_name()
            fields = {
                "id": "TEXT",
                "content_vector": "VECTOR",
            }

            if type(self.vector_scheme_attributes) is dict and len(self.vector_scheme_attributes)>0:
                for key, value in self.vector_scheme_attributes.items():
                    # TODO: Add support for other types
                    fields[value] = "TEXT"

            print("*************** Index:", fields)

            Config.vector_db_connector.create_redis_index(
                index_name=index_name,
                fields=fields,
                prefix=index_name,
            )
        except Exception as e:
            print(e)
            raise e

    def embedding(self, obj:Dict[str,Any]) -> Any:
        """
        Convert the object to embedding.
        """
        try:
            if type(obj) is not dict or len(obj)<1 and len(self.embedding_attributes) < 1:
                return None
            
            data = []

            for key in self.embedding_attributes:
                if key in obj:
                    data.append(obj[key])

            if len(data) < 1:
                data = obj

            return Config.proxy_large_model.provider.get_embeddings(json.dumps(data))

        except Exception as e:
            print(e)
            return None

    def save_document_chuck(
            self, 
            raw:str, 
            document_uuid: str,
            document_title:str, 
            document_external_id:str, 
            embeddings: Any,
            chunk_index:int = 0,
            editor:str = "",
            max_retries: int = 3,
        ):
        """
        Save document chunk to dynamodb
        """
        retry_count = 0

        while retry_count < max_retries:
            try:
                now = pendulum.now("UTC")
                
                DocumentModel(
                    document_source=self.document_source,
                    document_uuid=f"{document_uuid}",
                    document_external_id=f"{document_external_id}",
                    endpoint_id=self.endpoint_id,
                    document_title=f"{document_title} ",
                    document_content=raw,
                    chunk_index=chunk_index,
                    title_embedding=embeddings,
                    content_embedding=embeddings,
                    created_at=now,
                    updated_at=now,
                    updated_by=editor,
                ).save()
                
                print(f"\n\n=================== Save data to dynamodb successful: {document_uuid}")
                break
            except Exception as e:
                retry_count += 1
                print(f"Error: {e}")
                print(f"Retrying... Attempt {retry_count}")
                time.sleep(2 ** retry_count)

    def save_vector_document(self, obj: Dict[str, Any], documentId: str, embedding: Any):
        """
        Save vector document to vector database
        """
        try:
            document = {
                "id": documentId,
                "content_vector": embedding,
                "name": "",
            }

            if type(self.vector_scheme_attributes) is dict and len(self.vector_scheme_attributes) > 0:
                for k,v in self.vector_scheme_attributes.items():
                    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>",obj.get(k, ""))
                    document[v] = obj.get(k, "")

            print(f"\n\n=================== Save vector document successful: {documentId}")
            print(self._generate_vector_database_index_name())
            print(document)
            
            Config.vector_db_connector.index_document(
                prefix=self._generate_vector_database_index_name(),
                key="id",
                doc=document,
            )
        except Exception as e:
            print(e)
            raise e
    def save_graph_document(self, entities:Dict[str, Any]):
        """
        Extract entities from the given object and save them to the graph database.
        """
        try:
            print("\n\n=================== Graph Entities")
            print("\n>>>>>>>>>> 1. Extracted Entities:", entities)
            
            if type(entities) is not dict or len(entities) < 1:
                return
            
            print(f"\n>>>>>>>>>> 2. Extracted Entities Verify: {entities}")
            
            # cypher_query = self._generate_cypher_statments(entities)

            # print(f"\n>>>>>>>>>> 2. Generated Cypher Statment: {cypher_query}")

            # if type(cypher_query) is str and len(cypher_query) > 0:
            #     print(f"\n>>>>>>>>>> 4. Excute Cypher Query: {cypher_query}\n\n")
            #     with Config.graph_db_connector.driver.session(
            #         database=Config.graph_db_connector.database
            #     ) as session:
            #         session.run(cypher_query)
            #     # session.close()
            #     print("\n=================== Save graph document successful")
            cypher_query_list = self._generate_cypher_upsert_statments(entities)
            print(f"\n --------- Cypher query list --------: {cypher_query_list}")
            if cypher_query_list:
                for cypher_query in cypher_query_list:
                    with Config.graph_db_connector.driver.session(
                        database=Config.graph_db_connector.database
                    ) as session:
                        session.run(cypher_query.get('query'), nodes = cypher_query.get('nodes'))

        except Exception as e:
            raise e