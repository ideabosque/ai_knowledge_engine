#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..handlers.handlers import resolve_data_view_handler
from ..types.data_view import DataViewType


def resolve_data_view(info: ResolveInfo, **kwargs: Dict[str, Any]) -> DataViewType:
    return resolve_data_view_handler(info, **kwargs)