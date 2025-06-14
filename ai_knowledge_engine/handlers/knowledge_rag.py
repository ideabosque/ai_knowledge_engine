#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import logging
import traceback
from typing import Any, Callable, Dict, List, Tuple

from graphene import ResolveInfo
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from silvaengine_utility import Utility

from ..models.request import RequestModel, insert_update_request
from ..models.knowledge_graph_metadata import _get_enabled_knowledge_graph_metadata
from ..types.knowledge_rag import KnowledgeRagType
from .config import Config
from .error import InsufficientDetailsError, SchemaRetrievalError


def _get_embedding(text: str) -> List[Dict[str, Any]]:
    text = text.replace("\n", " ")
    return Config.proxy_large_model.provider.get_embeddings(text)


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
    print(f"----------merge_rule...:{merge_rule}")
    try:
        vector_merge_key = merge_rule["vector_merge_key"]
        graph_merge_node = merge_rule["graph_merge_node"]
        graph_merge_key = merge_rule["graph_merge_key"]
        vector_attributes = merge_rule["vector_attributes_to_include"]

        # Extract transaction IDs from vector results for lookup
        transaction_ids = []
        valid_vector_results = []
        for vector_item in vector_results:
            if not vector_item.get(vector_merge_key):
                continue
            transaction_ids.append(f"{vector_item.get(vector_merge_key)}")
            valid_vector_results.append(vector_item)

        if not transaction_ids:
            return []
        print(f"\n---transaction_ids : {transaction_ids}\n")

        cypher_query = _generate_cypher_query(
            f"""Retrieve the node ({graph_merge_node}) associated with `{graph_merge_key}` within the specified `{transaction_ids}`. Return the node as `node`.""",
            Config.graph_schema,
        )

        logger.info(f"Generated Cypher query for bulk lookup: {cypher_query}")

        # Execute the Cypher query
        _, graph_results = Config.graph_db_connector.execute_cypher_query_with_pagination(
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
        for vector_item in valid_vector_results:
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
    return Config.proxy_large_model.provider.is_similarity_search(
        user_query, Config.system_contents["is_similarity_search"], Config.graph_schema
    )


# Use AI to generate Cypher query dynamically based on schema
def _generate_cypher_query(user_query: str, graph_schema: str) -> str:
    return Config.proxy_large_model.provider.generate_cypher_query(
        user_query, Config.system_contents["generate_cypher_query"], graph_schema
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(
        (SchemaRetrievalError, InsufficientDetailsError)
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

        return Config.graph_db_connector.execute_cypher_query_with_pagination(
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
        print(f"\n--------query_vector...: {len(query_vector)}")
        if len(query_vector) == 0:
            raise Exception("Query vector is empty!")
        return Config.vector_db_connector.search_vector(query_vector, index_name, **kwargs)
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

    print(f"is_similarity_search...:{is_similarity_search}")
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
        print(f"\n --------vector_results...: {vector_results_total} : {vector_results}")

        merged_results = _lookup_and_merge_results(
            logger,
            Utility.json_loads(Utility.json_dumps(vector_results)),
            knowledge_graph_metadata.merge_rule,
        )

        return KnowledgeRagType(results=merged_results, total=vector_results_total)

    # Retrieve the total count and first batch of results
    cypher_query = _generate_cypher_query(user_query, Config.graph_schema)
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
