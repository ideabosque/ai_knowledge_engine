#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from ..handlers.user_memory import UserMemoryHandler
from ..types.long_term_memory import LongTermMemoryType



def resolve_long_term_memory(info: ResolveInfo, **kwargs: Dict[str, Any]) -> LongTermMemoryType:
    try:
        user_data = {
            "user_id": kwargs.get("user_id"),
            "user_query": kwargs.get("user_query", ""),
            "query_context": kwargs.get("query_context", {})
        }
        user_memory_data = UserMemoryHandler(info).get_long_term_memory(user_data)
    except Exception as e:
        print(e)
        log = traceback.format_exc()
        info.context.get("logger").error(log)
        raise e

    return user_memory_data

