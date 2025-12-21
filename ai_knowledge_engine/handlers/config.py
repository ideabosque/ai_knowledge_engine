import boto3, logging, sys, os, traceback, zipfile, tempfile, atexit
from typing import Dict, List, Any, Optional, Callable
from silvaengine_utility import Utility, Serializer
from ..providers.proxy_large_model import ProxyLargeModel
from ..models import utils

class Config:
    openai_client = None
    openai_model = None
    graph_db_connector = None
    vector_db_connector = None
    redis_index_config = None
    graph_schema = None
    system_contents = None
    module_bucket_name = None
    module_zip_path = None
    module_extract_path = None
    aws_s3 = None
    aws_s3_bucket = None
    embedding_model = None
    aws_lambda = None
    graphql_schemes = {}
    test_mode = None
    process_model = None
    # spacy_nlp = None
    # spacy_nlp_trf = None
    proxy_large_model = None

    @classmethod
    def initialize(cls, logger: logging.Logger, **setting: Dict[str, Any]) -> None:
        """
        Initialize configuration setting.
        Args:
            logger (logging.Logger): Logger instance for logging.
            **setting (Dict[str, Any]): Configuration dictionary.
        """
        try:
            cls._setup_parameters(setting)
            cls._setup_function_paths(setting)
            cls._initialize_aws_services(setting)
            cls._initialize_process_model(setting)
            cls._initialize_graph_database(logger, setting)
            cls._initialize_vector_database(logger, setting)
            # cls._initialize_fetch_graphql_schema(
            #     setting,
            #     function_name="ai_knowledge_graphql",
            #     logger=logging.Logger("ai_knowledge_graphql"),
            # )
            if setting.get("test_mode") == "local_for_all":
                cls._initialize_tables(logger)
            logger.info("Configuration initialized successfully.")
        except Exception as e:
            logger.exception("Failed to initialize configuration.")
            raise e
        finally:
            atexit.register(cls._cleanup)
            logger.info("Cleanup registered to atexit.")


    @classmethod
    def _setup_parameters(cls, setting: Dict[str, Any]) -> None:
        cls.process_model = setting.get("process_model", "spacy")
        if "EMBEDDING_MODEL" in setting:
            cls.embedding_model = setting["EMBEDDING_MODEL"]
        if "openai_model" in setting:
            cls.openai_model = setting["openai_model"]
        if "system_contents" in setting:
            cls.system_contents = setting["system_contents"]

        cls.test_mode = setting.get("test_mode", None)


    @classmethod
    def _setup_function_paths(cls, setting: Dict[str, Any]) -> None:
        cls.module_bucket_name = setting.get("module_bucket_name")
        cls.module_zip_path = setting.get("module_zip_path", "/tmp/adaptor_zips")
        cls.module_extract_path = setting.get("module_extract_path", "/tmp/adaptors")
        os.makedirs(cls.module_zip_path, exist_ok=True)
        os.makedirs(cls.module_extract_path, exist_ok=True)


    @classmethod
    def _initialize_aws_services(cls, setting: Dict[str, Any]) -> None:
        if all(
            setting.get(k)
            for k in ["region_name", "aws_access_key_id", "aws_secret_access_key"]
        ):
            aws_credentials = {
                "region_name": setting["region_name"],
                "aws_access_key_id": setting["aws_access_key_id"],
                "aws_secret_access_key": setting["aws_secret_access_key"],
            }
        else:
            aws_credentials = {}

        cls.aws_lambda = boto3.client("lambda", **aws_credentials)
        cls.aws_s3_bucket = setting.get("swap_bucket_name")
        cls.aws_s3 = boto3.client("s3", **aws_credentials)


    @classmethod
    def _initialize_process_model(cls, setting: Dict[str, Any]) -> None:
        cls.proxy_large_model = ProxyLargeModel(cls.aws_s3, **setting)
        # if "openai" == cls.process_model:
        #     cls._initialize_openai_client(setting)
        # elif "spacy" == cls.process_model:
        #     cls._initialize_spacy_compenent(setting)


    # @classmethod
    # def _initialize_spacy_compenent(cls, setting: Dict[str, Any]) -> None:
    #     import spacy

    #     model_bucket = setting.get("model_bucket_name", "silvaengine-models")
    #     tmp_dir = tempfile.mkdtemp()

    #     # TODO: Parallelize the download and decompression of the following models.
    #     model_name = setting.get("spacy_model", "en_core_web_sm")
    #     key = f"{model_name}.zip"
    #     zip_path = f"{tmp_dir}/{key}"
    #     model_path = f"{tmp_dir}/{model_name}"

    #     cls.aws_s3.download_file(model_bucket, key, zip_path)

    #     # Extract the ZIP file
    #     with zipfile.ZipFile(zip_path, "r") as zip_ref:
    #         zip_ref.extractall(model_path)

    #     cls.spacy_nlp = spacy.util.load_model_from_path(model_path)

    #     trf_model_name = setting.get("spacy_trf_model", "en_core_web_trf")
    #     key = f"{trf_model_name}.zip"
    #     zip_path = f"{tmp_dir}/{key}"
    #     trf_model_path = f"{tmp_dir}/{trf_model_name}"

    #     cls.aws_s3.download_file(model_bucket, key, zip_path)

    #     # Extract the ZIP file
    #     with zipfile.ZipFile(zip_path, "r") as zip_ref:
    #         zip_ref.extractall(trf_model_path)

    #     cls.spacy_nlp_trf = spacy.util.load_model_from_path(trf_model_path)


    @classmethod
    def _initialize_openai_client(cls, setting: Dict[str, Any]) -> None:
        from openai import OpenAI

        if "openai_api_key" in setting:
            openai_setting = {"api_key": setting["openai_api_key"]}

            if "openai_base_url" in setting:
                openai_setting.update({"base_url": setting["openai_base_url"]})

            cls.openai_client = OpenAI(**openai_setting)


    @classmethod
    def _initialize_graph_database(cls, logger: logging.Logger, setting: Dict[str, Any]) -> None:
        if "graph_db_connector_config" in setting:
            cls.graph_db_connector = cls.get_class_object(
                logger,
                setting["graph_db_connector_config"]["module_name"],
                setting["graph_db_connector_config"]["class_name"],
                **setting["graph_db_connector_config"]["setting"],
            )
            cls.graph_schema = cls.graph_db_connector.get_graph_schema()


    @classmethod
    def _initialize_vector_database(
        cls, logger: logging.Logger, setting: Dict[str, Any]
    ) -> None:
        if "vector_db_connector_config" in setting:
            cls.vector_db_connector = cls.get_class_object(
                logger,
                setting["vector_db_connector_config"]["module_name"],
                setting["vector_db_connector_config"]["class_name"],
                **dict(
                    setting["vector_db_connector_config"]["setting"],
                    **{
                        "openai_api_key": setting["openai_api_key"],
                        "EMBEDDING_MODEL": cls.embedding_model,
                    },
                ),
            )


    @classmethod
    def _initialize_fetch_graphql_schema(
        cls,
        setting: Dict[str, Any],
        function_name: str,
        logger: logging.Logger = None,
    ) -> Dict[str, Any]:

        endpoint_id = setting.get("endpoint_id")
        if cls.graphql_schemes.get(function_name) is None:
            cls.graphql_schemes[function_name] = Utility.fetch_graphql_schema(
                logger,
                endpoint_id,
                function_name,
                setting=setting,
                aws_lambda=cls.aws_lambda,
                test_mode=cls.test_mode,
            )

        return cls.graphql_schemes[function_name]


    @classmethod
    def _initialize_tables(cls, logger: logging.Logger) -> None:
        """
        Initialize database tables by calling the utils._initialize_tables() method.
        This is an internal method used during configuration setup.
        """
        utils._initialize_tables(logger)


    @classmethod
    def get_class_object(
        cls, logger: logging.Logger, module_name: str, class_name: str, **setting: Dict[str, Any]
    ) -> Optional[Callable]:
        try:
            if not cls._module_exists(logger, module_name):
                # Download and extract the module if it doesn't exist
                cls._download_and_extract_module(logger, module_name)

            # Add the extracted module to sys.path
            module_path = f"{Config.module_extract_path}/{module_name}"
            if module_path not in sys.path:
                sys.path.append(module_path)

            _class = getattr(__import__(module_name), class_name)

            return _class(
                logger,
                **Serializer.json_normalize(setting),
            )
        except Exception as e:
            log = traceback.format_exc()
            logger.error(log)
            raise e


    @classmethod
    def _module_exists(cls, logger: logging.Logger, module_name: str) -> bool:
        """Check if the module exists in the specified path."""
        module_dir = os.path.join(cls.module_extract_path, module_name)
        if os.path.exists(module_dir) and os.path.isdir(module_dir):
            logger.info(f"Module {module_name} found in {cls.module_extract_path}.")
            return True
        logger.info(f"Module {module_name} not found in {cls.module_extract_path}.")
        return False


    @classmethod
    def _download_and_extract_module(cls, logger: logging.Logger, module_name: str) -> None:
        """Download and extract the module from S3 if not already extracted."""
        key = f"{module_name}.zip"
        zip_path = f"{cls.module_zip_path}/{key}"

        logger.info(f"Downloading module from S3: bucket={cls.module_bucket_name}, key={key}")
        cls.aws_s3.download_file(cls.module_bucket_name, key, zip_path)
        logger.info(f"Downloaded {key} from S3 to {zip_path}")

        # Extract the ZIP file
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(cls.module_extract_path)
        logger.info(f"Extracted module to {cls.module_extract_path}")


    @classmethod
    def _cleanup(cls):
        if hasattr(cls, 'graph_db_connector') and cls.graph_db_connector is not None:
            cls.graph_db_connector.close()
            print("Neo4j driver closed.")
        if hasattr(cls, 'vector_db_connector') and cls.vector_db_connector is not None:
            cls.vector_db_connector.redis_client.close()
            print("Redis connector closed.")