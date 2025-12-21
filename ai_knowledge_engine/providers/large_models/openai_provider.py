import json, re
from typing import Any, Dict
from openai import OpenAI
from .abstract_model import AbstractModel
from ...handlers.error import InsufficientDetailsError, SchemaRetrievalError


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

        return self.base_query(user_prompt, system_prompt, format="json")


    def base_query(self, user_input, system_prompt, format: str = "") -> Any:
        response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {"role": "system", "content":system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        content = response.choices[0].message.content
        result = json.loads(content) if format == "json" and isinstance(content, str) else content
        return result


    def tokenize_text(self, text: str) -> Dict[str, Any]:
        prompt = f"Please tokenize the user-submitted text and return it strictly as a JSON array. "
        return json.loads(self.base_query(self._clean_data(text), prompt))


    def get_embeddings(self, data) -> Any:
        embeddings = self.openai_client.embeddings.create(
            input=data, model=self.embedding_model
        )
        return embeddings.data[0].embedding


    def is_similarity_search(self, user_query: str, system_prompt: str, graph_schema) -> bool:
        """Check if the user query indicates a similarity search."""
        user_prompt = f"Is this query ({user_query}) a similarity search based on schema: ({graph_schema})?"
        is_similarity_search = self.base_query(user_prompt, system_prompt)
        if is_similarity_search.startswith(
            "The query is ambiguous and does not provide enough information to determine if it pertains to a similarity search. Please provide additional context or clarify your intent."
        ):
            raise InsufficientDetailsError(is_similarity_search)

        if is_similarity_search == "true":
            return True
        return False


    def generate_cypher_query(self, user_query: str, system_prompt, graph_schema) -> str:
        user_prompt = f"Generate a Cypher query for: {user_query} using schema: {graph_schema}"
        cypher_query = self.base_query(user_prompt, system_prompt)

        if cypher_query.startswith("Unable to retrieve the graph schema."):
            raise SchemaRetrievalError(cypher_query)

        if cypher_query.startswith("Could you provide more details?"):
            raise InsufficientDetailsError(cypher_query)

        return cypher_query


    """
    ############## private methods ##############
    """

    def _clean_data(self, text: str) -> str:
        """
        Data cleaning to remove noisy information
        """
        return re.sub(r'\s+', ' ', text).strip()
