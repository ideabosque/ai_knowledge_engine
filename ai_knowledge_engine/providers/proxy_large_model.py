from ai_knowledge_engine.ai_knowledge_engine.handlers.config import Config
from .large_models import AbstractModel, SpacyProvider, OpenaiProvider


class ProxyLargeModel(object):
    provider = None

    def __init__(self) -> None:
        if Config.process_model.get("provider") == "openai":
            provider = OpenaiProvider()
        elif Config.process_model.get("provider") == "spacy":
            provider = SpacyProvider()
        else:
            raise Exception("Invalid provider")
        self.provider = provider


    def get_provider(self) -> AbstractModel:
        return self.provider
