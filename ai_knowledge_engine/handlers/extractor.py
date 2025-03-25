
import json, re
from typing import Any, Dict, List
from .config import Config

class Extractor:
    def __init__(self, document_source: str, attributes: Dict[str, Any]):
        self.graph_scheme = Config.graph_db_connector.get_graph_schema()
        self.graph_scheme_attributes = attributes
        self.attributes = list(attributes.values())

        self._completion_graph_scheme_attributes(document_source=document_source,attributes=attributes)

    def extract_entities(self, user_prompt: str) -> Dict[str, Any]:
        """
        Extracting entities, attributes, and relationships from data for graph
        """
        try:
            system_prompt = f"""Please strictly follow the following data mapping rules and schemes to extract the corresponding information and relationships from the user-provided data:
1. Mapping rule - Mapping rules for fields in user data and scheme fields (The key in the rule corresponds to the user's original data source, and the value corresponds to the key in the scheme.):
{self.graph_scheme_attributes}

2. Enter - One line of CSV data, which may contain the following entities or relationships in the scheme:
{self.graph_scheme}

3. Output requirements (strictly JSON format):
{{
    "entities": [
        {{"id": 1, "type": "Person", "name": "John Doe", "properties": {"age":30}, ...}},
        {{"id": 2, "type": "Location", "name": "New York", ...}},
        {{"id": 3, "type": "Organization", "name": "Apple", ...}},
        {{"id": 4, "type": "Product", "name": "Apple", "type": "abc", ...}}
        ...
    ],
    "relationships": [
        {{"from": 1, "to": 3, "type": "WORK_AT", "properties": {{"position":"Engineer"}},
        {{"from": 1, "to": 2, "type": "LIVE_IN"}}
        ...
    ]
}}"""
            response = Config.openai_client.chat.completions.create(
                model=Config.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            return json.loads(response.choices[0].message.content)
        except:
            return None

    
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
        try:
            prompt = f"Please tokenize the user-submitted text and return it strictly as a JSON array. "
            response = Config.openai_client.chat.completions.create(
                model=Config.openai_model,
                messages=[
                    {"role": "system", "content":prompt},
                    {"role": "user", "content": self.clean_data(text)}
                ]
            )

            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return []