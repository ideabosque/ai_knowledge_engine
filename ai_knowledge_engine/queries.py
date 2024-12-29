#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from .handlers import (
    resolve_data_source_handler,
    resolve_data_source_list_handler,
    resolve_document_handler,
    resolve_document_list_handler,
    resolve_document_process_entity_handler,
    resolve_document_process_entity_list_handler,
    resolve_document_process_task_handler,
    resolve_document_process_task_list_handler,
    resolve_knowledge_graph_metadata_handler,
    resolve_knowledge_graph_metadata_list_handler,
    resolve_request_handler,
    resolve_request_list_handler,
)
from .types import (
    DataSourceListType,
    DataSourceType,
    DocumentListType,
    DocumentProcessEntityListType,
    DocumentProcessEntityType,
    DocumentProcessTaskListType,
    DocumentProcessTaskType,
    DocumentType,
    KnowledgeGraphMetadataListType,
    KnowledgeGraphMetadataType,
    RequestListType,
    RequestType,
)


def resolve_document(info: ResolveInfo, **kwargs: Dict[str, Any]) -> DocumentType:
    return resolve_document_handler(info, **kwargs)


def resolve_document_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentListType:
    return resolve_document_list_handler(info, **kwargs)


def resolve_document_process_task(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessTaskType:
    return resolve_document_process_task_handler(info, **kwargs)


def resolve_document_process_task_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessTaskListType:
    return resolve_document_process_task_list_handler(info, **kwargs)


def resolve_document_process_entity(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessEntityType:
    return resolve_document_process_entity_handler(info, **kwargs)


def resolve_document_process_entity_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessEntityListType:
    return resolve_document_process_entity_list_handler(info, **kwargs)


def resolve_data_source(info: ResolveInfo, **kwargs: Dict[str, Any]) -> DataSourceType:
    return resolve_data_source_handler(info, **kwargs)


def resolve_data_source_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DataSourceListType:
    return resolve_data_source_list_handler(info, **kwargs)


def resolve_knowledge_graph_metadata(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeGraphMetadataType:
    return resolve_knowledge_graph_metadata_handler(info, **kwargs)


def resolve_knowledge_graph_metadata_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeGraphMetadataListType:
    return resolve_knowledge_graph_metadata_list_handler(info, **kwargs)


def resolve_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> RequestType:
    return resolve_request_handler(info, **kwargs)


def resolve_request_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> RequestListType:
    return resolve_request_list_handler(info, **kwargs)
