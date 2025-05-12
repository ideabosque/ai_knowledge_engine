import json, re
from typing import Any, Dict
from openai import OpenAI
from .abstract_model import AbstractModel


class OpenaiProvider(AbstractModel):
    openai_client = None
    openai_model = None
    embedding_model = None

    def __init__(self, **setting: Dict[str, Any]) -> None:
        if "openai_api_key" not in setting:
            raise Exception("openai_api_key is required")

        openai_setting = {"api_key": setting["openai_api_key"]}
        if "openai_base_url" in setting:
            openai_setting.update({"base_url": setting["openai_base_url"]})
        self.openai_client = OpenAI(**openai_setting)

        if "openai_model" in setting:
            self.openai_model = setting["openai_model"]
        if "EMBEDDING_MODEL" in setting:
            self.embedding_model = setting["EMBEDDING_MODEL"]


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

        return json.loads(self._base_query(user_prompt, system_prompt))


    def tokenize_text(self, text: str) -> Dict[str, Any]:
        prompt = f"Please tokenize the user-submitted text and return it strictly as a JSON array. "
        return json.loads(self._base_query(self._clean_data(text), prompt))


    def get_embeddings(self, data) -> Any:
        embeddings = self.openai_client.embeddings.create(
            input=json.dumps(data), model=self.embedding_model
        )
        return embeddings.data[0].embedding


    """
    ############## private methods ##############
    """
    def _base_query(self, user_input, system_prompt):
        response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {"role": "system", "content":system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        return response.choices[0].message.content


    def _clean_data(self, text: str) -> str:
        """
        Data cleaning to remove noisy information
        """
        return re.sub(r'\s+', ' ', text).strip()
