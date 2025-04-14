#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import (
    Boolean,
    DateTime,
    Decimal,
    Field,
    Float,
    Int,
    List,
    ObjectType,
    String,
)

from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class DocumentProcessTaskType(ObjectType):
    document_source = JSON()
    process_task_uuid = String()
    process_status = String()
    process_note = String()
    cut_time = DateTime()
    start_time = DateTime()
    end_time = DateTime()


class DocumentProcessTaskListType(ListObjectType):
    document_process_task_list = List(DocumentProcessTaskType)
