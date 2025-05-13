from typing import Any, Dict

class AbstractModel(object):

    def extract_entities(self, user_prompt: str, graph_scheme, graph_scheme_attributes) -> Dict[str, Any]:
        raise NotImplementedError("Subclasses must implement this method")


    def tokenize_text(self, text: str) -> Dict[str, Any]:
        raise NotImplementedError("Subclasses must implement this method")


    def get_embeddings(self, data) -> Any:
        raise NotImplementedError("Subclasses must implement this method")
