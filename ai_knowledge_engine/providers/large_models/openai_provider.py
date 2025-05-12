import json, re
from typing import Any, Dict
from ai_knowledge_engine.ai_knowledge_engine.handlers.config import Config
from .abstract_model import AbstractModel


class OpenaiProvider(AbstractModel):
    def extract_entities(self, user_prompt: str, graph_scheme, graph_scheme_attributes) -> Dict[str, Any]:
        system_prompt = f"""Please strictly follow the following data mapping rules and schemes to extract the corresponding information and relationships from the user-provided data:
1. Mapping rule - Mapping rules for fields in user data and scheme fields (The key in the rule corresponds to the user's original data source, and the value corresponds to the key in the scheme.):
{graph_scheme_attributes}

2. Enter - One line of CSV data, which may contain the following entities or relationships in the scheme:
{graph_scheme}

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


    def tokenize_text(self, text: str) -> Dict[str, Any]:
        prompt = f"Please tokenize the user-submitted text and return it strictly as a JSON array. "
        response = Config.openai_client.chat.completions.create(
            model=Config.openai_model,
            messages=[
                {"role": "system", "content":prompt},
                {"role": "user", "content": self.clean_data(text)}
            ]
        )
        return json.loads(response.choices[0].message.content)
