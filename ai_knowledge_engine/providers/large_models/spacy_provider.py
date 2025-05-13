import json, zipfile, tempfile
from typing import Any, Dict
import spacy
from spacy.matcher import PhraseMatcher
from .abstract_model import AbstractModel



class SpacyProvider(AbstractModel):
    spacy_nlp = None
    sentence_trf = None


    def __init__(self, aws_s3, **setting: Dict[str, Any]) -> None:

        # TODO: Parallelize the download and decompression of the following models.
        model_name = setting.get("spacy_model", "en_core_web_sm")
        try:
            self.spacy_nlp = spacy.load(model_name)
        except OSError as e:
            model_bucket = setting.get("model_bucket_name", "silvaengine-models")
            tmp_dir = tempfile.mkdtemp()
            key = f"{model_name}.zip"
            zip_path = f"{tmp_dir}/{key}"
            model_path = f"{tmp_dir}/{model_name}"

            aws_s3.download_file(model_bucket, key, zip_path)

            # Extract the ZIP file
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(model_path)

            self.spacy_nlp = spacy.util.load_model_from_path(model_path)

        # trf_model_name = setting.get("spacy_trf_model", "en_core_web_trf")
        # key = f"{trf_model_name}.zip"
        # zip_path = f"{tmp_dir}/{key}"
        # trf_model_path = f"{tmp_dir}/{trf_model_name}"

        # aws_s3.download_file(model_bucket, key, zip_path)

        # # Extract the ZIP file
        # with zipfile.ZipFile(zip_path, "r") as zip_ref:
        #     zip_ref.extractall(trf_model_path)

        # self.spacy_nlp_trf = spacy.util.load_model_from_path(trf_model_path)

        # self.sentence_trf = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')


    def extract_entities(self, user_prompt: str, graph_scheme, graph_scheme_attributes) -> Dict[str, Any]:
        result = self._find_similar_keys_and_extract(user_prompt, graph_scheme_attributes, 0.7)
        # result = self._spacy_structured_extraction(text)
        print(f"\n----find_similar_keys_and_extract--------:\n{result}")
        # return None
        print(f"\n--graph_scheme--: {graph_scheme} \n")
        # format result to graph_scheme format
        entities = []
        scheme_entities = graph_scheme.get("entities", {})
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


    def tokenize_text(self, text: str) -> Dict[str, Any]:
        doc = self.spacy_nlp(text)
        tokens = []
        for token in doc:
            tokens.append(token.text,)

        return tokens


    def get_embeddings(self, data) -> Any:
        embeddings = self.spacy_nlp(data).vector.tolist()
        return embeddings


    def is_similarity_search(self, user_query: str, system_prompt: str, graph_schema) -> bool:
        """Check if the user query indicates a similarity search."""
        return False


    def generate_cypher_query(self, user_query: str, system_prompt, graph_schema) -> str:
        return ""


    """
    ############## private methods ##############
    """
    def _find_similar_keys_and_extract(self, target_dict, graph_scheme_attributes, threshold=0.7):
        """
        Match the key with high similarity in the dictionary based on the field list and extract the corresponding value
        params:
            target_dict: "{key: value}"
            threshold: similarity range(0-1)
        results:
            dicts
        """
        nlp = self.spacy_nlp
        print(f"\n------nlp --------:{nlp.__module__}")
        results = {}

        target_dict = json.loads(target_dict)
        dict_keys = list(target_dict.keys())
        dict_key_docs = {key: nlp(key) for key in dict_keys}
        
        field_list = list(graph_scheme_attributes.keys())
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
            response[graph_scheme_attributes[field]] = results[field][0]['value']

        return dict(response)


    def _spacy_structured_extraction(self, text, graph_scheme_attributes):
        nlp = self.spacy_nlp
        doc = nlp(text)
        print(f"doc-------------:\n{doc}")
        
        # init matcher
        matcher = PhraseMatcher(nlp.vocab)
        matcher.add("Product".upper(), list(nlp.pipe(list(graph_scheme_attributes.keys()))))

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
