#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"


class SchemaRetrievalError(Exception):
    """Raised when the graph schema cannot be retrieved."""

    pass


class InsufficientDetailsError(Exception):
    """Raised when insufficient details are provided in the user query."""

    pass