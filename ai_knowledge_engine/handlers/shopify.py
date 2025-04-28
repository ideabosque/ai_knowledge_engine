import json
import traceback
import uuid
import pendulum
import logging
import humps
import time
from graphene import ResolveInfo
from typing import Any,  Dict, List
from .parser import Parser
from .config import Config
from .extractor import Extractor
from .operator import Operator
from ..utils import text_util
from shopify_connector import ShopifyConnector


class ShopifyHandler:
    def __init__(self, setting: Dict[str, Any], logger: logging.Logger):
        self.setting = setting
        self.structured_data = []
        self.unstructured_data = []
        self.entity_cache = []  # For staging entities, attributes, and relationships
        self.token_count = 0
        self.logger = logger
        self.shopify_connector = ShopifyConnector(logger, **self.setting)


    def process_data(
            self,
            info: ResolveInfo,
            document_source: str,
            endpoint_id: str,
            position: int = 0,
            embedding_attributes: List[str] = [],
            graph_scheme_attributes: Dict[str, str] = {},
            vector_scheme_attributes: Dict[str, str] = {},
            max_retries: int = 3,
            editor: str = "",
            filters: Dict[str, Any] = {},
            document_external_id: str = None
        ):
        if document_source == "product":
            self.process_products(
                info,
                endpoint_id,
                position,
                embedding_attributes,
                graph_scheme_attributes,
                vector_scheme_attributes,
                max_retries,
                editor,
                filters,
                document_external_id
            )

    def process_products(
            self, 
            info: ResolveInfo, 
            endpoint_id: str, 
            position: int = 0,
            embedding_attributes: List[str] = [],
            graph_scheme_attributes: Dict[str, str] = {},
            vector_scheme_attributes: Dict[str, str] = {},
            max_retries: int = 3,
            editor: str = "",
            filters: Dict[str, Any] = {},
            document_external_id: str = None
        ):
        """
        Read S3 files line by line and process data
        """
        document_source = "product"
        document_title = f"Processed Shopify Products <{Config}>"
        extractor = Extractor(document_source=document_source, attributes=graph_scheme_attributes)
        operator = Operator(
            document_source=document_source, 
            endpoint_id=endpoint_id, 
            graph_scheme_attributes=graph_scheme_attributes,
            vector_scheme_attributes=vector_scheme_attributes,
            embedding_attributes=embedding_attributes,
        )
        products = self.get_all_products(last_id=position, filters=filters)
        print(f"shopify response-----------\n : {products}")
        if not products:
            self.logger.warning("No products found from Shopify")
            return

        if document_external_id is None:
            document_external_id = uuid.uuid4().hex

        try:
            for item in products:
                try:
                    document_uuid = uuid.uuid4().hex
                    obj = self._product_to_dict(item)
                    # print(f"obj-----------\n : {obj}")
                    embedding = operator.embedding(obj=obj)
                    # print(f"embedding-----------\n : {embedding}")
                    # print("\n----------------extract_entities start: ")
                    # print(extractor.extract_entities(json.dumps(obj)))
                    # print("\n----------------extract_entities end: ")

                    # 1. Write data to vector database
                    operator.save_vector_document(obj, document_uuid, embedding)
                    # 2. Save data to dynamodb
                    operator.save_document_chuck(
                        raw=obj,
                        document_uuid=document_uuid,
                        document_title=document_title,
                        document_external_id=document_external_id,
                        embeddings=embedding,
                        editor=editor,
                        max_retries=max_retries,
                    )
                    # 3. Extract entities & write entitis to graph database
                    operator.save_graph_document(extractor.extract_entities(json.dumps(obj)))

                except Exception as e:
                    print(traceback.format_exc())
                    continue
        except Exception as e:
            print(f"Skip: {e}")
            pass


    def _product_to_dict(self, product) -> Dict[str, Any]:
        return {
            "id": product.id,
            "product_name": product.title,
            "handle": product.handle,
            "meta_description": text_util.remove_html_tags(product.body_html) if product.body_html else "",
            "category": product.product_type if product.product_type else "",
            "meta_keywords": product.tags if product.tags else "",
            "brand_name": product.vendor if product.vendor else "",
            "price": product.variants[0].price if len(product.variants) > 0 else "",
            "product_code/sku": product.variants[0].sku if len(product.variants) > 0 else "",
        }

    def get_page_products(self, last_id: int = 0, limit: int = 100, filters: Dict[str, Any] = {}):
        try:
            attributes = {
                # "created_at_max": "2025-03-26T16:15:47-04:00",
                # "created_at_min": "2025-02-25T16:15:47-04:00",
                # "product_type": "Boxing",
                "fields": "handle,id,title,body_html,vendor,product_type,tags,variants",
                "limit": limit,
                "since_id": last_id,
                "status": "active",
                "order":"id asc",
                ** filters
            }
            products = self.shopify_connector.find_products_by_attributes(attributes)
            return products

        except Exception as e:
            print(f"Erorr: {e}")

        return []


    def get_all_products(self, last_id: int = 0, filters: Dict[str, Any] = {}):
        all_products = []
        limit = 100
        while True:
            try:
                products = self.get_page_products(last_id=last_id, limit=limit, filters=filters)
                if not products:
                    break

                all_products.extend(products)
                last_id = products[-1].id
                if len(products) < limit:
                    break
                # API call limit 2/s 
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Erorr: {e}")
                time.sleep(5)
                continue

        return all_products
