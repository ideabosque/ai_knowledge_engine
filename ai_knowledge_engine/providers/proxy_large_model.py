from typing import Any, Dict
from .large_models.abstract_model import AbstractModel
# from .large_models.spacy_provider import SpacyProvider
from .large_models.openai_provider import OpenaiProvider
from .large_models.ollama_provider import OllamaProvider
from .large_models.ollama_cloud_provider import OllamaCloudProvider


class ProxyLargeModel(object):
    provider: AbstractModel = None

    def __init__(self, aws_s3_client, **setting: Dict[str, Any]) -> None:
        process_model = setting.get("process_model", "spacy")

        if process_model == "openai":
            self.provider = OpenaiProvider(**setting)
        # elif process_model == "spacy":
        #     self.provider = SpacyProvider(aws_s3_client, **setting)
        elif process_model == "ollama":
            self.provider = OllamaProvider(aws_s3_client, **setting)
        elif process_model == "ollama_cloud":
            self.provider = OllamaCloudProvider(**setting)
        else:
            raise Exception("Invalid provider")
