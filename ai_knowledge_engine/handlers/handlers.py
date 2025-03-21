#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import json
import logging
import os
import re
import sys
import traceback
import uuid
import zipfile
from typing import Any, Callable, Dict, List, Optional, Tuple

import boto3
import pendulum
import tiktoken
from graphene import ResolveInfo
from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from silvaengine_utility import Utility

from ..models.request import RequestModel, insert_update_request
from ..models.data_source import get_data_source
from ..models.knowledge_graph_metadata import _get_enabled_knowledge_graph_metadata
from ..types.knowledge_rag import KnowledgeRagType
from ..types.data_view import DataViewType


class SchemaRetrievalError(Exception):
    """Raised when the graph schema cannot be retrieved."""

    pass


class InsufficientDetailsError(Exception):
    """Raised when insufficient details are provided in the user query."""

    pass


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


def handlers_init(logger: logging.Logger, **setting: Dict[str, Any]) -> None:
    try:
        global embedding_model, openai_model, system_contents
        global module_bucket_name, module_zip_path, module_extract_path
        global aws_s3, aws_s3_bucket
        global openai_client
        global graph_db_connector, graph_schema
        global vector_db_connector, redis_index_config

        _setup_parameters(setting)
        _setup_function_paths(setting)
        _initialize_aws_services(setting)
        _initialize_openai_client(setting)
        _initialize_graph_database(logger, setting)
        _initialize_vector_database(logger, setting)

    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


def _setup_parameters(setting: Dict[str, Any]) -> None:
    global embedding_model, openai_model, system_contents

    if "EMBEDDING_MODEL" in setting:
        embedding_model = setting["EMBEDDING_MODEL"]
    if "openai_model" in setting:
        openai_model = setting["openai_model"]
    if "system_contents" in setting:
        system_contents = setting["system_contents"]


def _initialize_aws_services(setting: Dict[str, Any]) -> None:
    global aws_s3, aws_s3_bucket

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

    aws_s3_bucket = setting.get("swap_bucket_name")
    aws_s3 = boto3.client("s3", **aws_credentials)


def _initialize_openai_client(setting: Dict[str, Any]) -> None:
    global openai_client

    if "openai_api_key" in setting:
        openai_setting = {"api_key": setting["openai_api_key"]}

        if "openai_base_url" in setting:
            openai_setting.update({"base_url": setting["openai_base_url"]})

        openai_client = OpenAI(**openai_setting)


def _initialize_graph_database(logger: logging.Logger, setting: Dict[str, Any]) -> None:
    global graph_db_connector, graph_schema
    if "graph_db_connector_config" in setting:
        graph_db_connector = _get_class_object(
            logger,
            setting["graph_db_connector_config"]["module_name"],
            setting["graph_db_connector_config"]["class_name"],
            **setting["graph_db_connector_config"]["setting"],
        )
        graph_schema = graph_db_connector.get_graph_schema()


def _initialize_vector_database(
    logger: logging.Logger, setting: Dict[str, Any]
) -> None:
    global vector_db_connector, redis_index_config
    if "vector_db_connector_config" in setting:
        vector_db_connector = _get_class_object(
            logger,
            setting["vector_db_connector_config"]["module_name"],
            setting["vector_db_connector_config"]["class_name"],
            **dict(
                setting["vector_db_connector_config"]["setting"],
                **{
                    "openai_api_key": setting["openai_api_key"],
                    "EMBEDDING_MODEL": embedding_model,
                },
            ),
        )


def _setup_function_paths(setting: Dict[str, Any]) -> None:
    global module_bucket_name, module_zip_path, module_extract_path
    module_bucket_name = setting.get("module_bucket_name")
    module_zip_path = setting.get("module_zip_path", "/tmp/adaptor_zips")
    module_extract_path = setting.get("module_extract_path", "/tmp/adaptors")
    print(module_zip_path, module_extract_path)
    os.makedirs(module_zip_path, exist_ok=True)
    os.makedirs(module_extract_path, exist_ok=True)


def _module_exists(logger: logging.Logger, module_name: str) -> bool:
    """Check if the module exists in the specified path."""
    module_dir = os.path.join(module_extract_path, module_name)
    print(f"----------------{module_dir}-----")
    if os.path.exists(module_dir) and os.path.isdir(module_dir):
        logger.info(f"Module {module_name} found in {module_extract_path}.")
        return True
    logger.info(f"Module {module_name} not found in {module_extract_path}.")
    return False


def _download_and_extract_module(logger: logging.Logger, module_name: str) -> None:
    """Download and extract the module from S3 if not already extracted."""
    key = f"{module_name}.zip"
    zip_path = f"{module_zip_path}/{key}"

    logger.info(f"Downloading module from S3: bucket={module_bucket_name}, key={key}")
    aws_s3.download_file(module_bucket_name, key, zip_path)
    logger.info(f"Downloaded {key} from S3 to {zip_path}")

    # Extract the ZIP file
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(module_extract_path)
    logger.info(f"Extracted module to {module_extract_path}")


def _get_class_object(
    logger: logging.Logger, module_name: str, class_name: str, **setting: Dict[str, Any]
) -> Optional[Callable]:
    try:
        if not _module_exists(logger, module_name):
            # Download and extract the module if it doesn't exist
            _download_and_extract_module(logger, module_name)

        # Add the extracted module to sys.path
        module_path = f"{module_extract_path}/{module_name}"
        if module_path not in sys.path:
            sys.path.append(module_path)

        _class = getattr(__import__(module_name), class_name)

        return _class(
            logger,
            **Utility.json_loads(Utility.json_dumps(setting)),
        )
    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


def _get_embedding(text: str) -> List[Dict[str, Any]]:
    text = text.replace("\n", " ")
    res = openai_client.embeddings.create(input=[text], model=embedding_model)
    return res.data[0].embedding


def _lookup_and_merge_results(
    logger: logging.Logger,
    vector_results: List[Dict[str, Any]],
    merge_rule: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Perform a lookup in the graph database for each vector result and merge the results based on the specified merge rule.

    Args:
        vector_results (List[Dict[str, Any]]): The results from the vector search.
        merge_rule (Dict[str, Any]): The rules defining how to merge vector and graph data.
        logger (Any): The logger instance for logging information and errors.

    Returns:
        List[Dict[str, Any]]: The merged results, combining vector and graph data.
    """
    try:
        vector_merge_key = merge_rule["vector_merge_key"]
        graph_merge_node = merge_rule["graph_merge_node"]
        graph_merge_key = merge_rule["graph_merge_key"]
        vector_attributes = merge_rule["vector_attributes_to_include"]

        # Extract transaction IDs from vector results for lookup
        transaction_ids = [
            f"{vector_item.get(vector_merge_key)}"
            for vector_item in vector_results
            if vector_item.get(vector_merge_key)
        ]

        if not transaction_ids:
            return []

        cypher_query = _generate_cypher_query(
            f"""Retrieve the node ({graph_merge_node}) associated with `{graph_merge_key}` within the specified `{transaction_ids}`. Return the node as `node`.""",
            graph_schema,
        )

        logger.info(f"Generated Cypher query for bulk lookup: {cypher_query}")

        # Execute the Cypher query
        _, graph_results = graph_db_connector.execute_cypher_query_with_pagination(
            cypher_query,
            limit=len(transaction_ids),
            skip=0,
            get_total=False,
        )

        # Organize graph results into a lookup dictionary
        graph_lookup = {}
        for result in graph_results:
            key = result["node"].get(
                graph_merge_key
            )  # Adjust based on how the node key is identified
            if key not in graph_lookup:
                # Include all attributes from the node
                graph_lookup[key] = {
                    **result["node"],  # Unpack all attributes of the node
                }

        # Merge vector results with corresponding graph data
        merged_results = []
        for vector_item in vector_results:
            merged_item = {vector_merge_key: vector_item.get(vector_merge_key)}

            # Add vector attributes to the merged result
            merged_item.update(
                {
                    attr: vector_item.get(attr)
                    for attr in vector_attributes
                    if attr in vector_item
                }
            )

            # Add graph attributes if available
            graph_data = graph_lookup.get(vector_item.get(vector_merge_key), {})
            merged_item.update(graph_data)

            merged_results.append(merged_item)

        return merged_results

    except Exception as e:
        logger.error(f"Error during lookup and merge: {traceback.format_exc()}")
        raise e


def _is_similarity_search(user_query: str) -> bool:
    """Check if the user query indicates a similarity search."""
    response = openai_client.chat.completions.create(
        model=openai_model,
        messages=[
            {
                "role": "system",
                "content": system_contents["is_similarity_search"],
            },
            {
                "role": "user",
                "content": f"Is this query ({user_query}) a similarity search based on schema: ({graph_schema})?",
            },
        ],
    )
    is_similarity_search = response.choices[0].message.content

    if is_similarity_search.startswith(
        "The query is ambiguous and does not provide enough information to determine if it pertains to a similarity search. Please provide additional context or clarify your intent."
    ):
        raise InsufficientDetailsError(is_similarity_search)

    if is_similarity_search == "true":
        return True
    return False


# Use AI to generate Cypher query dynamically based on schema
def _generate_cypher_query(user_query: str, graph_schema: str) -> str:
    response = openai_client.chat.completions.create(
        model=openai_model,
        messages=[
            {
                "role": "system",
                "content": system_contents["generate_cypher_query"],
            },
            {
                "role": "user",
                "content": f"Generate a Cypher query for: {user_query} using schema: {graph_schema}",
            },
        ],
    )
    cypher_query = response.choices[0].message.content

    if cypher_query.startswith("Unable to retrieve the graph schema."):
        raise SchemaRetrievalError(cypher_query)

    if cypher_query.startswith("Could you provide more details?"):
        raise InsufficientDetailsError(cypher_query)

    return cypher_query


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(
        lambda e: not isinstance(e, (SchemaRetrievalError, InsufficientDetailsError))
    ),
    reraise=True,
)
def _query_graph(
    logger: logging.Logger,
    document_source: str,
    request_uuid: str,
    cypher_query: str,
    offset: int,
    limit: int,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Executes a query on the graph database."""
    try:
        # Retrieve the total count and first batch of results
        request = RequestModel.get(document_source, request_uuid)
        request.cypher_query = cypher_query
        request.save()

        return graph_db_connector.execute_cypher_query_with_pagination(
            cypher_query,
            limit=limit,
            skip=offset,
            get_total=True,
        )
    except Exception as e:
        logger.error(f"Graph query failed: {traceback.format_exc()}")
        raise e


def _query_vector(
    logger: logging.Logger, user_query: str, index_name: str, **kwargs: Dict[str, Any]
) -> Tuple[int, List[Dict[str, Any]]]:
    """Executes a query on the vector search engine."""
    try:
        query_vector = _get_embedding(user_query)
        return vector_db_connector.search_vector(query_vector, index_name, **kwargs)
    except Exception as e:
        logger.error(f"Vector query failed: {traceback.format_exc()}")
        raise e


# Define the updated function and helper methods
def _process_and_merge_results(
    logger: logging.Logger, **kwargs: Dict[str, Any]
) -> KnowledgeRagType:
    # Extract parameters from kwargs
    user_query = kwargs.get("user_query")
    document_source = kwargs.get("document_source")
    request_uuid = kwargs.get("request_uuid")
    is_similarity_search = kwargs.get("is_similarity_search")

    # Retrieve metadata and merge results
    knowledge_graph_metadata = _get_enabled_knowledge_graph_metadata(document_source)
    index_name = f"{knowledge_graph_metadata.endpoint_id}:{knowledge_graph_metadata.document_source}"
    logger.info(f"Index name: {index_name}")

    if is_similarity_search:
        _kwargs = {
            "vector_field": kwargs.get("vector_field"),
            "fields_to_return": kwargs.get("fields_to_return"),
            **{
                key: kwargs[key]
                for key in ["filter_conditions", "top_k", "result_offset", "limit"]
                if key in kwargs
            },
        }

        vector_results_total, vector_results = _query_vector(
            logger, user_query, index_name, **_kwargs
        )

        merged_results = _lookup_and_merge_results(
            logger,
            Utility.json_loads(Utility.json_dumps(vector_results)),
            knowledge_graph_metadata.merge_rule,
        )

        return KnowledgeRagType(results=merged_results, total=vector_results_total)

    # Retrieve the total count and first batch of results
    cypher_query = _generate_cypher_query(user_query, graph_schema)
    logger.info(f"Generated Cypher query: {cypher_query}")

    # Query functions
    graph_results_total, graph_results = _query_graph(
        logger,
        document_source,
        request_uuid,
        cypher_query,
        kwargs.get("offset", 0),
        kwargs.get("limit", 100),
    )

    return KnowledgeRagType(results=graph_results, total=graph_results_total)


def request_decorator() -> Callable:
    def actual_decorator(original_function: Callable) -> Callable:
        @functools.wraps(original_function)
        def wrapper_function(*args: List, **kwargs: Dict[str, any]) -> Any:
            try:
                cols = {
                    "document_source": kwargs["document_source"],
                    "user_query": kwargs["user_query"],
                    "updated_by": "system",
                }
                request = insert_update_request(args[0], **cols)

                is_similarity_search = kwargs.get("is_similarity_search")
                if is_similarity_search is None:
                    is_similarity_search = _is_similarity_search(kwargs["user_query"])
                    kwargs["is_similarity_search"] = is_similarity_search
                cols.update({"is_similarity_search": is_similarity_search})

                kwargs["request_uuid"] = request.request_uuid

                result = original_function(*args, **kwargs)

                cols.update(
                    {
                        "request_uuid": request.request_uuid,
                        "results": result.results,
                    }
                )
                request = insert_update_request(args[0], **cols)

                return result
            except Exception as e:
                log = traceback.format_exc()
                cols.update(
                    {
                        "request_uuid": request.request_uuid,
                        "request_note": log,
                    }
                )
                request = insert_update_request(args[0], **cols)
                args[0].context.get("logger").error(log)

                raise e

        return wrapper_function

    return actual_decorator


@request_decorator()
def resolve_knowledge_rag_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeRagType:
    return _process_and_merge_results(info.context.get("logger"), **kwargs)


def _get_data_adaptor_function(
    logger: logging.Logger,
    data_source_type: str,
    data_source_name: str,
    function_name: str,
) -> Optional[Callable]:
    try:
        data_source = get_data_source(data_source_type, data_source_name)

        configuration = (
            data_source.configuration.__dict__["attribute_values"]
            if data_source.__dict__["attribute_values"].get("configuration")
            else {}
        )

        setting = dict(configuration, **{"data_views": data_source.data_views})

        class_object = _get_class_object(
            logger, data_source.module_name, data_source.class_name, **setting
        )

        return getattr(
            class_object,
            function_name,
        )
    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


def resolve_data_view_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DataViewType:
    data_source_type = kwargs.get("data_source_type")
    data_source_name = kwargs.get("data_source_name")
    data_view_name = kwargs.get("data_view_name")
    parameters = kwargs.get("parameters", {})

    try:
        data_view_function = _get_data_adaptor_function(
            info.context.get("logger"),
            data_source_type,
            data_source_name,
            "get_data_view",
        )
        data_view = data_view_function(data_view_name, **parameters)

        return DataViewType(**data_view)
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").error(log)
        raise e
