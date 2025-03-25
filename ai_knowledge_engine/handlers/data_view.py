#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple

from graphene import ResolveInfo

from ..models.data_source import get_data_source
from ..types.data_view import DataViewType
from .config import Config


def _get_data_adaptor_function(
    logger: logging.Logger,
    endpoint_id: str,
    data_source_name: str,
    function_name: str,
) -> Optional[Callable]:
    try:
        data_source = get_data_source(endpoint_id, data_source_name)

        configuration = (
            data_source.configuration.__dict__["attribute_values"]
            if data_source.__dict__["attribute_values"].get("configuration")
            else {}
        )

        setting = dict(configuration, **{"data_views": data_source.data_views})

        class_object = Config.get_class_object(
            logger, data_source.module_name, data_source.class_name, **setting
        )

        return getattr(
            class_object,
            function_name,
        )
    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


def resolve_data_view_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DataViewType:
    data_source_name = kwargs.get("data_source_name")
    data_view_name = kwargs.get("data_view_name")
    parameters = kwargs.get("parameters", {})

    try:
        data_view_function = _get_data_adaptor_function(
            info.context.get("logger"),
            info.context.get("endpoint_id"),
            data_source_name,
            "get_data_view",
        )
        data_view = data_view_function(data_view_name, **parameters)

        return DataViewType(**data_view)
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").error(log)
        raise e
