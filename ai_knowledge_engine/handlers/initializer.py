import boto3, logging, sys, os, traceback, zipfile
from typing import Dict, List, Any, Optional, Callable
from openai import OpenAI
from silvaengine_utility import Utility

class Initializer:
    def __init__(self, setting: Dict[str, Any]):
        self.setting = setting
        self.graphql_schemes = {}
        self.test_mode = setting.get("test_mode")

        if "EMBEDDING_MODEL" in setting:
            self.embedding_model = setting["EMBEDDING_MODEL"]
        if "openai_model" in setting:
            self.openai_model = setting["openai_model"]
        if "system_contents" in setting:
            self.system_contents = setting["system_contents"]

        self._setup_function_paths()
        self._initialize_aws_services()
        self._initialize_openai_client()
        self._initialize_graph_database()
        self._initialize_vector_database()
        self.fetch_graphql_schema(
            endpoint_id=self.setting.get("endpoint_id"), 
            function_name="ai_knowledge_graphql",
            logger=logging.Logger("ai_knowledge_graphql"),
        )

    def _initialize_aws_services(self) -> None:
        """
        Initialize AWS services
        """
        if all(
            self.setting.get(k)
            for k in ["region_name", "aws_access_key_id", "aws_secret_access_key"]
        ):
            aws_credentials = {
                "region_name": self.setting["region_name"],
                "aws_access_key_id": self.setting["aws_access_key_id"],
                "aws_secret_access_key": self.setting["aws_secret_access_key"],
            }
        else:
            aws_credentials = {}

        self.aws_lambda = boto3.client("lambda")
        self.aws_s3_bucket = self.setting.get("swap_bucket_name")
        self.aws_s3 = boto3.client("s3", **aws_credentials)

    def _initialize_openai_client(self) -> None:
        """
        Initialize OpenAI client
        """
        if "openai_api_key" in self.setting:
            openai_setting = {"api_key": self.setting["openai_api_key"]}
            if "openai_base_url" in self.setting:
                openai_setting.update({"base_url": self.setting["openai_base_url"]})
            self.openai_client = OpenAI(**openai_setting)

    def _initialize_graph_database(self, logger: logging.Logger = None) -> None:
        """
        Initialize graph database
        """
        if "graph_db_connector_config" in self.setting:
            self.graph_db_connector = self._get_class_object(
                logger,
                self.setting["graph_db_connector_config"]["module_name"],
                self.setting["graph_db_connector_config"]["class_name"],
                **self.setting["graph_db_connector_config"]["setting"],
            )
            self.graph_schema = self.graph_db_connector.get_graph_schema()

    def _initialize_vector_database(self, logger: logging.Logger = None) -> None:
        """
        Initialize vector database
        """
        if "vector_db_connector_config" in self.setting:
            self.vector_db_connector = self._get_class_object(
                logger,
                self.setting["vector_db_connector_config"]["module_name"],
                self.setting["vector_db_connector_config"]["class_name"],
                **dict(
                    self.setting["vector_db_connector_config"]["setting"],
                    **{
                        "openai_api_key": self.setting["openai_api_key"],
                        "EMBEDDING_MODEL": self.embedding_model,
                    },
                ),
            )

    def _get_class_object(self, logger: logging.Logger, module_name: str, class_name: str, **setting: Dict[str, Any]) -> Optional[Callable]:
        """
        Get class object
        """
        try:
            if not self._module_exists(logger, module_name):
                # Download and extract the module if it doesn't exist
                self._download_and_extract_module(logger, module_name)
            # Add the extracted module to sys.path
            module_path = f"{self.module_extract_path}/{module_name}"
            if module_path not in sys.path:
                sys.path.append(module_path)
            _class = getattr(__import__(module_name), class_name)
            return _class(
                logger,
                **Utility.json_loads(Utility.json_dumps(setting)),
            )
        except Exception as e:
            log = traceback.format_exc()
            if logger:
                logger.error(log)
            raise e

    def _setup_function_paths(self) -> None:
        """
        Set up function paths
        """
        self.module_bucket_name = self.setting.get("module_bucket_name")
        self.module_zip_path = self.setting.get("module_zip_path", "/tmp/adaptor_zips")
        self.module_extract_path = self.setting.get("module_extract_path", "/tmp/adaptors")
        os.makedirs(self.module_zip_path, exist_ok=True)
        os.makedirs(self.module_extract_path, exist_ok=True)

    def _module_exists(self, logger: logging.Logger, module_name: str) -> bool:
        """
        Check if the module exists in the specified path.
        """
        module_dir = os.path.join(self.module_extract_path, module_name)
        if os.path.exists(module_dir) and os.path.isdir(module_dir):
            if logger:
                logger.info(f"Module {module_name} found in {self.module_extract_path}.")
            return True
        if logger:
            logger.info(f"Module {module_name} not found in {self.module_extract_path}.")
        return False

    def _download_and_extract_module(self, logger: logging.Logger, module_name: str) -> None:
        """
        Download and extract the module from S3 if not already extracted.
        """
        key = f"{module_name}.zip"
        zip_path = f"{self.module_zip_path}/{key}"
        if logger:
            logger.info(f"Downloading module from S3: bucket={self.module_bucket_name}, key={key}")
        self.aws_s3.download_file(self.module_bucket_name, key, zip_path)
        if logger:
            logger.info(f"Downloaded {key} from S3 to {zip_path}")
        # Extract the ZIP file
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(self.module_extract_path)
        if logger:
            logger.info(f"Extracted module to {self.module_extract_path}")

    def _clean_data(self, line: str) -> str:
        """
        Data cleaning to remove noisy information
        """
        return re.sub(r'\s+', ' ', line).strip()

    def _extract_entities_from_structured(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extracting entities, attributes, and relationships from structured data
        """
        entities = []
        for key, value in data.items():
            entities.append({"entity": key, "attribute": value, "relation": "HAS_ATTRIBUTE"})
        return entities

    def fetch_graphql_schema(
        self,
        endpoint_id: str,
        function_name: str,
        logger: logging.Logger = None,
    ) -> Dict[str, Any]:

        if self.graphql_schemes.get(function_name) is None:
            self.graphql_schemes[function_name] = Utility.fetch_graphql_schema(
                logger,
                endpoint_id,
                function_name,
                setting=self.setting,
                aws_lambda=self.aws_lambda,
        )
        return self.graphql_schemes[function_name]