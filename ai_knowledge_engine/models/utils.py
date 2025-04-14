# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List


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