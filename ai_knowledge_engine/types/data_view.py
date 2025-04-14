#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import (
    Boolean,
    Int,
    List,
    ObjectType,
    String,
)

from silvaengine_utility import JSON


class DataViewType(ObjectType):
    results = List(JSON)
    count = Int()
    has_more = Boolean()
    offset = Int()
    total = Int()
