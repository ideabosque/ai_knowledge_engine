#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import knowledge_graph_metadata
from ..types.knowledge_graph_metadata import KnowledgeGraphMetadataType, KnowledgeGraphMetadataListType


def resolve_knowledge_graph_metadata(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeGraphMetadataType:
    return knowledge_graph_metadata.resolve_knowledge_graph_metadata(info, **kwargs)


def resolve_knowledge_graph_metadata_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeGraphMetadataListType:
    return knowledge_graph_metadata.resolve_knowledge_graph_metadata_list(info, **kwargs)
