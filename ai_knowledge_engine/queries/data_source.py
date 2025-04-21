#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import data_source
from ..types.data_source import DataSourceType, DataSourceListType


def resolve_data_source(info: ResolveInfo, **kwargs: Dict[str, Any]) -> DataSourceType:
    return data_source.resolve_data_source(info, **kwargs)


def resolve_data_source_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DataSourceListType:
    return data_source.resolve_data_source_list(info, **kwargs)
