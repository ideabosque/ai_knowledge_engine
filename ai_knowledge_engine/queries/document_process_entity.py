#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import document_process_entity
from ..types.document_process_entity import DocumentProcessEntityType, DocumentProcessEntityListType


def resolve_document_process_entity(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessEntityType:
    return document_process_entity.resolve_document_process_entity(info, **kwargs)


def resolve_document_process_entity_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentProcessEntityListType:
    return document_process_entity.resolve_document_process_entity_list(info, **kwargs)
