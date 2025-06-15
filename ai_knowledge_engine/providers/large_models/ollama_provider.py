import json, re, requests
from typing import Any, Dict
from .abstract_model import AbstractModel
from ...utils.embedding import _tranform_embedding
from ...utils.text_util import _remove_html_tags


class OllamaProvider(AbstractModel):
    ollama_host = None
    ollama_model = None

    def __init__(self, **setting: Dict[str, Any]) -> None:
        if "ollama_host" not in setting:
            raise Exception("ollama_host is required")
        if "ollama_model" not in setting:
            raise Exception("ollama_model is required")

        self.ollama_host = setting["ollama_host"]
        self.ollama_model = setting["ollama_model"]


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
        user_prompt = _remove_html_tags(user_prompt)
        response = self._base_query(user_prompt, system_prompt)
        entities = []
        if "entities" in response:
            for entity in response["entities"]:
                for k in list(entity.keys()):
                    if entity[k] is None:
                        entity.pop(k)
                entities.append(entity)
        return {
            "entities": entities,
            "relationships": []
        }


    def tokenize_text(self, text: str) -> Dict[str, Any]:
        prompt = f"Please tokenize the user-submitted text and return it strictly as a JSON array. "
        response = self._base_query(self._clean_data(text), prompt)

        return response.get("tokens", [])


    def get_embeddings(self, data) -> Any:
        response = requests.post(
            self.ollama_host + "/api/embed",
            json={
                "model": self.ollama_model,
                "input": data
            }
        )
        # print(response.status_code, response.json())
        if response.status_code == 200:
            # original_embedding = response.json()["embeddings"][0]
            original_embeddings = response.json()["embeddings"]
            # load umap model and transform
            reduced_embeddings = _tranform_embedding(original_embeddings)
            return reduced_embeddings[0]
        else:
            print("request embedding failure:", response.text)
            return []


    def is_similarity_search(self, user_query: str, system_prompt: str, graph_schema) -> bool:
        """Check if the user query indicates a similarity search."""
        user_prompt = f"Is this query ({user_query}) a similarity search based on schema: ({graph_schema})?"
        response = self._base_query(user_prompt, system_prompt)

        if response and isinstance(response, dict):
            # dict key is not fixed
            for key, value in response.items():
                return value if isinstance(value, bool) else value == "true"
        return False


    def generate_cypher_query(self, user_query: str, system_prompt, graph_schema) -> str:
        user_prompt = f"Generate a Cypher query for: {user_query} using schema: {graph_schema}"
        cypher_query = self._base_query(user_prompt, system_prompt)

        # todo need debug
        return cypher_query.get("query") if  cypher_query.get("query") else ""


    """
    ############## private methods ##############
    """
    def _base_query(self, user_input, system_prompt):
        response = requests.post(
            self.ollama_host + "/api/chat",
            json={
                "model": self.ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                "stream": False,
                "format": "json",
                # "options": {
                #     "temperature": 0.7,
                #     "num_ctx": 2048
                # }
            }
        )
        # print(f"\n---------------ollam-response: ------\n {response}")
        if response.status_code == 200:
            # llama3.1
            json_str = response.json()["message"]["content"]
            json_result = json.loads(json_str)
            return json_result
        else:
            raise Exception("request failure: " + response.text)


    def _clean_data(self, text: str) -> str:
        """
        Data cleaning to remove noisy information
        """
        return re.sub(r'\s+', ' ', text).strip()
