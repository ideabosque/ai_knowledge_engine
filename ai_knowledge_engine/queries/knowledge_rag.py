#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..handlers.knowledge_rag import resolve_knowledge_rag_handler
from ..types.knowledge_rag import KnowledgeRagType


def resolve_knowledge_rag(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeRagType:
    print("\n-------resolve_knowledge_rag-----\n:", kwargs)
    return resolve_knowledge_rag_handler(info, **kwargs)