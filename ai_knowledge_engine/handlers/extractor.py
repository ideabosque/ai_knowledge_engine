
import json, re
from typing import Any, Dict, List
from .config import Config


class Extractor:
    def __init__(self, document_source: str, attributes: Dict[str, Any]):
        self.graph_scheme = Config.graph_db_connector.get_graph_schema()
        self.graph_scheme_attributes = attributes
        self.attributes = list(attributes.values())

        self._completion_graph_scheme_attributes(document_source=document_source,attributes=attributes)
        print(self.graph_scheme)
        print("\n----------graph_scheme_attributes-------------\n")
        print(self.graph_scheme_attributes)

    def extract_entities(self, user_prompt: str) -> Dict[str, Any]:
        """
        Extracting entities, attributes, and relationships from data for graph
        """
        response = Config.proxy_large_model.provider.extract_entities(
            user_prompt=user_prompt,
            graph_scheme=self.graph_scheme,
            graph_scheme_attributes=self.graph_scheme_attributes,
        )
        return response


    def _completion_graph_scheme_attributes(self, document_source: str, attributes: Dict[str, Any]):
        """
        Complete the graph scheme attributes with default values if they are not provided.
        """
        if type(attributes) is dict and len(attributes) > 0:
            entities = self.graph_scheme.get("entities", {})

            if len(entities) > 0:
                for label, entity in entities.items():
                    if label.lower() == document_source.lower() and "attributes" in entity and type(entity["attributes"]) is list:
                        self.graph_scheme["entities"][label]["attributes"] = list(set(entity["attributes"] + list(attributes.values())))
            else:
                self.graph_scheme["entities"][document_source.capitalize()] = {
                    "attributes": list(attributes.values())
                }

    
    def clean_data(self, text: str) -> str:
        """
        Data cleaning to remove noisy information
        """
        return re.sub(r'\s+', ' ', text).strip()


    def tokenize_text(self, text: str) -> List[str]:
        """
        Segmentation of unstructured data using OpenAI
        """
        response = Config.proxy_large_model.provider.tokenize_text(text)
        return response
