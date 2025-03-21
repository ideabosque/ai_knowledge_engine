#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict, List

from pynamodb.attributes import (
    BooleanAttribute,
    ListAttribute,
    MapAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
import pendulum
from tenacity import retry, stop_after_attempt, wait_exponential
from graphene import ResolveInfo
from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator
)
from silvaengine_utility import Utility
from ..types.knowledge_graph_metadata import KnowledgeGraphMetadataType, KnowledgeGraphMetadataListType
from .utils import _get_data_source


class KnowledgeGraphMetadataModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "ake-knowledge_graph_metadata"

    document_source = UnicodeAttribute(hash_key=True)
    metadata_version_uuid = UnicodeAttribute(range_key=True)
    endpoint_id = UnicodeAttribute()
    structured_data_views = ListAttribute(of=MapAttribute, null=True)
    structured_fields = ListAttribute(of=MapAttribute, null=True)
    unstructured_attributes = ListAttribute(of=MapAttribute, null=True)
    linkage_rules = ListAttribute(of=MapAttribute, null=True)
    merge_rule = MapAttribute(null=True)
    status = BooleanAttribute(default=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_knowledge_graph_metadata(
    document_source: str, metadata_version_uuid: str
) -> KnowledgeGraphMetadataModel:
    return KnowledgeGraphMetadataModel.get(document_source, metadata_version_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_enabled_knowledge_graph_metadata(
    document_source: str,
) -> KnowledgeGraphMetadataModel:
    try:
        results = KnowledgeGraphMetadataModel.query(
            document_source,
            None,
            filter_condition=(KnowledgeGraphMetadataModel.status == True),
            scan_index_forward=False,
            limit=1,
        )
        knowledge_graph_metadata = results.next()

        return knowledge_graph_metadata
    except StopIteration:
        return None


def get_knowledge_graph_metadata_count(
    document_source: str, metadata_version_uuid: str
) -> int:
    return KnowledgeGraphMetadataModel.count(
        document_source,
        KnowledgeGraphMetadataModel.metadata_version_uuid == metadata_version_uuid,
    )


def get_knowledge_graph_metadata_type(
    info: ResolveInfo, knowledge_graph_metadata: KnowledgeGraphMetadataModel
) -> KnowledgeGraphMetadataType:
    try:
        document_source = _get_data_source(
            knowledge_graph_metadata.endpoint_id,
            knowledge_graph_metadata.document_source,
        )
        structured_data_views = [
            {
                "data_source": _get_data_source(
                    structured_data_view["endpoint_id"],
                    structured_data_view["data_source_name"],
                ),
                "data_view_name": structured_data_view.get("data_view_name"),
                "adaptor_filter_attribute": structured_data_view.get(
                    "adaptor_filter_attribute"
                ),
                "graph_node_label": structured_data_view.get("graph_node_label"),
            }
            for structured_data_view in knowledge_graph_metadata.structured_data_views
        ]
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    knowledge_graph_metadata = knowledge_graph_metadata.__dict__["attribute_values"]
    knowledge_graph_metadata["document_source"] = document_source
    knowledge_graph_metadata["structured_data_views"] = structured_data_views
    knowledge_graph_metadata.pop("endpoint_id")
    return KnowledgeGraphMetadataType(
        **Utility.json_loads(Utility.json_dumps(knowledge_graph_metadata))
    )


def resolve_knowledge_graph_metadata(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeGraphMetadataType:
    if "metadata_version_uuid" in kwargs:
        return get_knowledge_graph_metadata_type(
            info,
            get_knowledge_graph_metadata(
                kwargs.get("document_source"), kwargs.get("metadata_version_uuid")
            ),
        )

    return get_knowledge_graph_metadata_type(
        info,
        _get_enabled_knowledge_graph_metadata(kwargs.get("document_source")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["document_source", "metadata_version_uuid"],
    list_type_class=KnowledgeGraphMetadataListType,
    type_funct=get_knowledge_graph_metadata_type,
)
def resolve_knowledge_graph_metadata_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    document_source = kwargs.get("document_source")
    endpoint_id = info.context["endpoint_id"]
    status = kwargs.get("status")
    args = []
    inquiry_funct = KnowledgeGraphMetadataModel.scan
    count_funct = KnowledgeGraphMetadataModel.count
    if document_source:
        args = [document_source, None]
        inquiry_funct = KnowledgeGraphMetadataModel.query

    the_filters = None  # We can add filters for the query.
    if endpoint_id:
        the_filters &= KnowledgeGraphMetadataModel.endpoint_id == endpoint_id
    if status:
        the_filters &= KnowledgeGraphMetadataModel.status == status
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


def _disable_knowledge_graph_metadatas(info: ResolveInfo, document_source: str) -> None:
    try:
        knowledge_graph_metadatas = KnowledgeGraphMetadataModel.query(
            document_source,
            None,
            filter_condition=KnowledgeGraphMetadataModel.status == True,
        )
        for knowledge_graph_metadata in knowledge_graph_metadatas:
            knowledge_graph_metadata.status = False
            knowledge_graph_metadata.save()
        return
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").error(log)
        raise e


@insert_update_decorator(
    keys={
        "hash_key": "document_source",
        "range_key": "metadata_version_uuid",
    },
    model_funct=get_knowledge_graph_metadata,
    count_funct=get_knowledge_graph_metadata_count,
    type_funct=get_knowledge_graph_metadata_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_knowledge_graph_metadata(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> KnowledgeGraphMetadataType:
    document_source = kwargs.get("document_source")
    metadata_version_uuid = kwargs.get("metadata_version_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context["endpoint_id"],
            "status": True,
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }

        enabled_knowledge_graph_metadata = _get_enabled_knowledge_graph_metadata(
            document_source
        )
        if enabled_knowledge_graph_metadata:
            cols.update(
                {
                    k: v
                    for k, v in enabled_knowledge_graph_metadata.__dict__[
                        "attribute_values"
                    ].items()
                    if k
                    not in [
                        "endpoint_id",
                        "status",
                        "updated_by",
                        "created_at",
                        "updated_at",
                    ]
                }
            )
            _disable_knowledge_graph_metadatas(info, document_source)

        for key in [
            "structured_data_views",
            "structured_fields",
            "unstructured_attributes",
            "linkage_rules",
            "merge_rule",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]

        KnowledgeGraphMetadataModel(
            document_source,
            metadata_version_uuid,
            **cols,
        ).save()
        return

    knowledge_graph_metadata = kwargs.get("entity")
    actions = [
        KnowledgeGraphMetadataModel.updated_by.set(kwargs["updated_by"]),
        KnowledgeGraphMetadataModel.updated_at.set(pendulum.now("UTC")),
    ]

    if "status" in kwargs and (
        kwargs["status"] == True and knowledge_graph_metadata.status == False
    ):
        _disable_knowledge_graph_metadatas(info, document_source)

    # Map of kwargs keys to KnowledgeGraphMetadataModel attributes
    field_map = {
        "structured_data_views": KnowledgeGraphMetadataModel.structured_data_views,
        "structured_fields": KnowledgeGraphMetadataModel.structured_fields,
        "unstructured_attributes": KnowledgeGraphMetadataModel.unstructured_attributes,
        "linkage_rules": KnowledgeGraphMetadataModel.linkage_rules,
        "merge_rule": KnowledgeGraphMetadataModel.merge_rule,
        "status": KnowledgeGraphMetadataModel.status,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the knowledge_graph_metadata
    knowledge_graph_metadata.update(actions=actions)

    return


@delete_decorator(
    keys={
        "hash_key": "document_source",
        "range_key": "metadata_version_uuid",
    },
    model_funct=get_knowledge_graph_metadata,
)
def delete_knowledge_graph_metadata(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> bool:
    if kwargs["entity"].status:
        results = KnowledgeGraphMetadataModel.query(
            kwargs["document_source"],
            None,
            filter_condition=KnowledgeGraphMetadataModel.status == False,
        )
        knowledge_graph_metadatas = [result for result in results]
        if len(knowledge_graph_metadatas) > 0:
            knowledge_graph_metadatas = sorted(
                knowledge_graph_metadatas, key=lambda x: x.updated_at, reverse=True
            )
            last_updated_record = knowledge_graph_metadatas[0]
            last_updated_record.status = True
            last_updated_record.save()

    kwargs["entity"].delete()

    return True
