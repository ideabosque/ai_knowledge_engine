#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import document_process_task
from ..types.document_process_task import DocumentProcessTaskType, DocumentProcessTaskListType


def resolve_document_process_task(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessTaskType:
    return document_process_task.resolve_document_process_task(info, **kwargs)


def resolve_document_process_task_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessTaskListType:
    return document_process_task.resolve_document_process_task_list(info, **kwargs)
