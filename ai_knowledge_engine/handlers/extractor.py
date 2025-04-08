
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
            if Config.process_model == "openai":
                response = Config.openai_client.chat.completions.create(
                    model=Config.openai_model,
                    messages=[
                        {"role": "system", "content":prompt},
                        {"role": "user", "content": self.clean_data(text)}
                    ]
                )

                return json.loads(response.choices[0].message.content)
            else :
                return self._transformers_tokenize_text(prompt, text)
        except json.JSONDecodeError:
            return []


    def _transformers_tokenize_text(self, prompt: str, text: str) -> List[str]:
        # from transformers import AutoModelForCausalLM, AutoTokenizer

        # tokenizer = AutoTokenizer.from_pretrained("gpt2-medium")
        # model = AutoModelForCausalLM.from_pretrained("gpt2-medium")

        # input_text = f"{prompt}\n\nUser: {self.clean_data(text)}\nAI:"
        # inputs = tokenizer(input_text, return_tensors="pt")
        # outputs = model.generate(**inputs, max_length=200)
        # print(f"outputs=========:{outputs}")
        # return tokenizer.decode(outputs[0], skip_special_tokens=True)

        return self.extract_entities_relations(text, prompt)
    

    def extract_entities_relations(self, text, system_prompt=None):
        result = self.find_similar_keys_and_extract(text, 0.7)
        print(f"\n----find_similar_keys_and_extract--------:\n{result}")
        print(f"\n--graph_scheme--: {self.graph_scheme} \n --attributes--: {self.attributes}")
        # todo format result to graph_scheme format
        return {
            "entities": [result],
            "relationships": []
        }
        nlp = Config.spacy_nlp_trf

        json_data = json.loads(text)
        print(f"\nsystem_prompt-----:{json_data}")
        # label, value in json_data.items():
            
        # Process system prompt to understand extraction targets
        prompt_doc = nlp(system_prompt)
        
        # Initialize target entity labels from prompt analysis
        target_entity_labels = set(
            ent.label_ for ent in prompt_doc.ents if ent.label_ in nlp.get_pipe("ner").labels
        )
        print(f"\ntarget_entity_labels----:{target_entity_labels}")

        # Apply NLP pipeline
        doc = nlp(text)
        
        # Initialize output structure
        result = {
            "entities": [],
            "relationships": []
        }
        
        # Custom entity processing
        entity_map = {}  # Track entities for relationship extraction
        
        # 1. Extract standard named entities
        for ent in doc.ents:
            if not target_entity_labels or ent.label_ in target_entity_labels:
                entity_id = len(result['entities']) + 1
                entity_map[ent.text] = entity_id
                result["entities"].append({
                    "id": entity_id,
                    "type": ent.label_,
                    "name": ent.text,
                    "source": "ner",
                    "properties": {
                        "start_pos": ent.start_char,
                        "end_pos": ent.end_char
                    }
                })

        return result


        # print(text)
        doc = Config.spacy_nlp_trf(text)
        
        # 
        entities = []
        for ent in doc.ents:
            print(ent.text)
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char
            })
        
        # 
        relations = []
        for token in doc:
            if token.dep_ in ("nsubj", "dobj", "attr"):
                relations.append({
                    "source": token.head.text,
                    "target": token.text,
                    "relation": token.dep_,
                    "sentence": token.sent.text
                })
        
        # 
        if system_prompt:
            prompt_doc = Config.spacy_nlp_trf(system_prompt)
            for ent in prompt_doc.ents:
                if any(e["text"] == ent.text for e in entities):
                    continue
                entities.append({
                    "text": ent.text,
                    "label": "PROMPT_" + ent.label_,
                    "start": None,
                    "end": None
                })
        
        return {"entities": entities, "relations": relations}


    def find_similar_keys_and_extract(self, target_dict, threshold=0.7):
        """
        Match the key with high similarity in the dictionary based on the field list and extract the corresponding value
        params:
            target_dict: {key: value}
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
        for field in results:
            results[field].sort(key=lambda x: x['similarity'], reverse=True)
            response[self.graph_scheme_attributes[field]] = results[field][0]['value']

        return dict(response)