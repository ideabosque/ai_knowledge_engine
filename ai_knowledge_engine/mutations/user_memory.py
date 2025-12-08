#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Int, Mutation, String, List
from silvaengine_utility import JSON

from ..handlers.user_memory import UserMemoryHandler


class ExtractUserMemory(Mutation):
    ok = Boolean()
    user_id = String()
    edges = List(JSON)
    preferences = List(JSON)
    interests = List(JSON)

    class Arguments:
        user_id = String(required=True)
        user_query = String(required=False)
        episodes = List(JSON, required=False)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "ExtractUserMemory":
        try:
            user_data = {
                "user_id": kwargs.get("user_id"),
                "episodes": kwargs.get("episodes", [])
            }
            user_memory_data = UserMemoryHandler(info).extract_user_memory(user_data)
        except Exception as e:
            print(user_data)
            print(e)
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return ExtractUserMemory(ok = True, **user_memory_data)


class ExtractLongTermMemory(Mutation):
    ok = Boolean()

    class Arguments:
        user_ids = List(String, required=True)
        interval_minutes = Int(required=False)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "ExtractLongTermMemory":
        try:
            user_data = {
                "user_ids": kwargs.get("user_ids", []),
                "interval_minutes": kwargs.get("interval_minutes", 60)
            }
            UserMemoryHandler(info).extract_long_term_memory(user_data)
        except Exception as e:
            print(user_data)
            print(e)
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return ExtractLongTermMemory(ok = True)
