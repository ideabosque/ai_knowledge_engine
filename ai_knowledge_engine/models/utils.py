# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
from typing import Any, Dict, List
from silvaengine_dynamodb_base import BaseModel


def _create_table(modelClass: BaseModel, logger: logging.Logger) -> bool:
    """Create the table if it doesn't exist."""
    # print(f"{modelClass.Meta.table_name} exists ------: {modelClass.exists()}")
    if not modelClass.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        modelClass.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The Agent table has been created.")
    return True


def _initialize_tables(logger: logging.Logger) -> None:
    from .data_source import DataSourceModel
    from .document_process_entity import DocumentProcessEntityModel
    from .document_process_task import DocumentProcessTaskModel
    from .document import DocumentModel
    from .knowledge_graph_metadata import KnowledgeGraphMetadataModel
    from .request import RequestModel
    from .document_process_error import DocumentProcessErrorModel

    _create_table(DataSourceModel, logger)
    _create_table(DocumentProcessEntityModel, logger)
    _create_table(DocumentProcessTaskModel, logger)
    _create_table(DocumentModel, logger)
    _create_table(KnowledgeGraphMetadataModel, logger)
    _create_table(RequestModel, logger)
    _create_table(DocumentProcessErrorModel, logger)


def _get_data_source(endpoint_id: str, data_source_name: str) -> Dict[str, Any]:
    from .data_source import get_data_source

    data_source = get_data_source(endpoint_id, data_source_name)
    return {
        "endpoint_id": endpoint_id,
        "data_source_name": data_source_name,
        "data_source_type": data_source.data_source_type,
        "module_name": data_source.module_name,
        "class_name": data_source.class_name,
        "configuration": data_source.configuration,
        "data_views": data_source.data_views,
    }


def _get_document_process_task(document_source: str, process_task_uuid: str) -> Dict[str, Any]:
    from .document_process_task import get_document_process_task

    document_process_task = get_document_process_task(document_source, process_task_uuid)
    return {
        "document_source": _get_data_source(
            document_process_task.endpoint_id, document_source
        ),
        "process_task_uuid": document_process_task.process_task_uuid,
        "process_status": document_process_task.process_status,
        "process_note": document_process_task.process_note,
        "cut_time": document_process_task.cut_time,
        "start_time": document_process_task.start_time,
        "end_time": document_process_task.end_time,
    }