
import json, re
from typing import Any, Dict, List
from .config import Config
from spacy.matcher import PhraseMatcher, Matcher
from spacy.tokens import Span


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
        response = Config.proxy_large_model.provider.extract_entities(
            user_prompt=user_prompt,
            graph_scheme=self.graph_scheme,
            graph_scheme_attributes=self.graph_scheme_attributes,
        )
        return response

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

            if Config.process_model == "openai":
                response = Config.openai_client.chat.completions.create(
                    model=Config.openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )

                return json.loads(response.choices[0].message.content)
            else :
                return self.extract_entities_relations(user_prompt, system_prompt)
        except Exception as e:
            print(f"Error in extract_entities: {e}")
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
        response = Config.proxy_large_model.provider.tokenize_text(text)
        return response
        try:
            if Config.process_model == "openai":
                prompt = f"Please tokenize the user-submitted text and return it strictly as a JSON array. "
                response = Config.openai_client.chat.completions.create(
                    model=Config.openai_model,
                    messages=[
                        {"role": "system", "content":prompt},
                        {"role": "user", "content": self.clean_data(text)}
                    ]
                )

                return json.loads(response.choices[0].message.content)
            else :
                return self._spacy_tokenize_text(text)
        except json.JSONDecodeError:
            return []


    def _spacy_tokenize_text(self, text: str) -> List[str]:
        doc = Config.spacy_nlp_trf(text)
        tokens = []
        for token in doc:
            tokens.append(token.text,)

        return tokens


    def extract_entities_relations(self, text, system_prompt=None):
        result = self.find_similar_keys_and_extract(text, 0.7)
        # result = self._spacy_structured_extraction(text)
        print(f"\n----find_similar_keys_and_extract--------:\n{result}")
        # return None
        print(f"\n--graph_scheme--: {self.graph_scheme} \n --attributes--: {self.attributes}")
        # format result to graph_scheme format
        entities = []
        scheme_entities = self.graph_scheme.get("entities", {})
        idx = 0
        for label, entity in scheme_entities.items():
            idx += 1
            entities.append({
                "id": result.get('id') if result.get("id") else idx,
                "type": label,
                "name": result.get("name", ""),
                "properties": ({attr : result.get(attr, "") for attr in entity.get("attributes", [])})
            })

        return {
            "entities": entities,
            "relationships": []
        }


    def find_similar_keys_and_extract(self, target_dict, threshold=0.7):
        """
        Match the key with high similarity in the dictionary based on the field list and extract the corresponding value
        params:
            target_dict: "{key: value}"
            threshold: similarity range(0-1)
        results:
            dicts
        """
        nlp = Config.spacy_nlp_trf
        print(f"\n------nlp --------:{nlp.__module__}")
        results = {}

        target_dict = json.loads(target_dict)
        dict_keys = list(target_dict.keys())
        dict_key_docs = {key: nlp(key) for key in dict_keys}
        
        field_list = list(self.graph_scheme_attributes.keys())
        print(f"\n------field_list --------:{field_list}")
        for field in field_list:
            field_doc = nlp(field)
            # calculate similarity
            for key, key_doc in dict_key_docs.items():
                # if not field_doc.vector.any() or not key_doc.vector.any():
                #     continue
                similarity = field_doc.similarity(key_doc)
                if similarity >= threshold:
                    if field not in results:
                        results[field] = []
                    results[field].append({
                        'matched_key': key,
                        'similarity': similarity,
                        'value': target_dict[key]
                    })
        
        # similarity sort and extract
        response = {}
        if target_dict.get("id"):
            response['id'] = target_dict['id']
        for field in results:
            results[field].sort(key=lambda x: x['similarity'], reverse=True)
            response[self.graph_scheme_attributes[field]] = results[field][0]['value']

        return dict(response)


    def _spacy_structured_extraction(self, text):
        nlp = Config.spacy_nlp_trf
        doc = nlp(text)
        print(f"doc-------------:\n{doc}")
        
        # init matcher
        matcher = PhraseMatcher(nlp.vocab)
        matcher.add("Product".upper(), list(nlp.pipe(list(self.graph_scheme_attributes.keys()))))

        results = {"matches": [], "attributes": []}
        matches = matcher(doc)
        print(f"matches-------------:\n{matches}")
        
        # keyword matching
        for match_id, start, end in matches:
            span = doc[start:end]
            print(f"\n----------span----:{span}")
            results["matches"].append({
                "text": span.text,
                "label": nlp.vocab.strings[match_id],
                "span": (start, end),
                "value": span.sent.text
            })

        return results