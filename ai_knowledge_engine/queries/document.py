#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import document
from ..types.document import DocumentType, DocumentListType


def resolve_document(info: ResolveInfo, **kwargs: Dict[str, Any]) -> DocumentType:
    return document.resolve_document(info, **kwargs)


def resolve_document_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DocumentListType:
    return document.resolve_document_list(info, **kwargs)