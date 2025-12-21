import json
from platform import system_alias
import uuid
import logging
import pendulum
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from ..handlers.config import Config
from ..models.short_term_memory import MemoryStatusEnums, insert_update_short_term_memory, get_short_term_memory, resolve_short_term_memory_list
from ..models.long_term_memory import insert_update_long_term_memory, get_long_term_memory, resolve_long_term_memory_list
from ..utils.text_util import md5_string


class UserMemoryHandler:
    """User Memory Handler - Process user conversation history, extract entity information, infer user preferences and save to Neo4j"""
    
    def __init__(self, info):
        self.info = info
        self.logger = info.context.get("logger")


    def extract_user_memory(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user memory data
        
        Args:
            user_data: User data containing user ID, session ID and conversation episodes
            
        Returns:
            Processing result containing edge relationships and user preferences
        """
        user_id = user_data.get("user_id")
        user_query = user_data.get("user_query")
        episodes = user_data.get("episodes", [])
        
        if not episodes or not isinstance(episodes, list):
            self.logger.error("No episodes found in user data")
            raise ValueError("No episodes found in user data")

        try:
            short_term_memories = []
            entities = []
            preferences = []
            interests = []
            message_uuids = [episode.get("message_uuid") for episode in episodes if episode.get("message_uuid")]
            if not message_uuids:
                self.logger.error("No message UUIDs found in episodes")
                raise ValueError("No message UUIDs found in episodes")

            # query history memory to extract entities and preferences
            stm_list = resolve_short_term_memory_list(
                self.info,
                **{
                    "user_uuid": user_id,
                    "message_uuids": message_uuids,
                    "limit": len(message_uuids),
                    # "start_time": episodes[0].get("message_time"),
                    # "end_time": episodes[-1].get("message_time"),
                }
            )
            history_memories = {}
            if stm_list is not None:
                for memory in stm_list.short_term_memory_list:
                    history_memories[memory.message_uuid] = memory

            # 1. Extract entity information and relationships
            for episode in episodes:
                message_uuid = episode.get("message_uuid")
                if not message_uuid:
                    self.logger.error("No message UUID found in episode")
                    raise ValueError("No message UUID found in episode")

                # query history memory to extract entities and preferences
                history_memory = history_memories.get(message_uuid)
                if history_memory is not None:
                    entities.extend(history_memory.entities)
                    preferences.extend(history_memory.preferences)
                    interests.extend(history_memory.interests)
                    continue

                memory_uuid = str(uuid.uuid4())
                entities_and_preferences = self._extract_entities_and_perferences(user_query, [episode])
                print(f"entities_and_preferences: {entities_and_preferences}")
                status = (MemoryStatusEnums.ACTIVE.value 
                    if entities_and_preferences.get("entities") or entities_and_preferences.get("preferences") 
                    else MemoryStatusEnums.INACTIVE.value)
                confidence = 0.0
                if entities_and_preferences.get("preferences"):
                    for preference in entities_and_preferences.get("preferences", []):
                        confidence = max(confidence, preference.get("confidence", 0.0))

                short_term_memories.append({
                    "user_uuid": user_id,
                    "memory_uuid": memory_uuid,
                    "thread_uuid": episode.get("thread_uuid", ""),
                    "message_uuid": episode.get("message_uuid", ""),
                    "profile": entities_and_preferences.get("profile", {}),
                    "entities": entities_and_preferences.get("entities", []),
                    "interests": entities_and_preferences.get("interests", []),
                    "preferences": entities_and_preferences.get("preferences", []),
                    "message_time": pendulum.parse(episode.get("message_time")).astimezone(pendulum.timezone("UTC")) if episode.get("message_time") else pendulum.now("UTC"),
                    "confidence": confidence,
                    "status": status,
                })
                entities.extend(entities_and_preferences.get("entities", []))
                preferences.extend(entities_and_preferences.get("preferences", []))
                interests.extend(entities_and_preferences.get("interests", []))

            # 2. Infer user preferences, merge and update historical user preferences
            # user_preferences = self._infer_user_preferences(user_data, entities_and_preferences)
            # print(f"user_preferences: {user_preferences}")

            # 2. Save short term memories to Neo4j
            for memory in short_term_memories:
                print(f"---memory------: {memory}")
                print(self.info)
                print(f"------------------")
                insert_update_short_term_memory(
                    self.info,
                    **memory
                )

            # 3. Return data structure
            return self._build_response(user_data, entities, preferences, interests)
            
        except Exception as e:
            print(e)
            self.logger.error(f"Failed to process user memory: {str(e)}")
            raise


    def extract_long_term_memory(self, user_data: Dict[str, Any]):
        """
        Process user memory data to extract long term memory
        
        Args:
            user_data: User data containing user ID, session ID and conversation episodes
            
        Returns:
            Processing result containing edge relationships and user preferences
        """
        user_ids = user_data.get("user_ids")

        for user_id in user_ids:
            try:
                ltm_list = resolve_long_term_memory_list(
                    self.info,
                    **{
                        "user_uuid": user_id,
                        "limit": 1,
                    }
                )
                last_memory = ltm_list.long_term_memory_list[0] if ltm_list and ltm_list.long_term_memory_list else None

                # query history memory to extract entities and preferences
                start_time = last_memory.last_stm_time if last_memory else None
                page_number = 1
                page_limit = 20
                new_ltm_data = {}
                while page_number < 1000:
                    short_term_memories = resolve_short_term_memory_list(
                        self.info,
                        **{
                            "user_uuid": user_id,
                            "start_time": start_time,
                            "ltm_version_id": "",
                            "page_number": page_number,
                            "status": MemoryStatusEnums.ACTIVE.value,
                            "min_confidence": 0.5,
                            "limit": page_limit
                        }
                    )
                    if not short_term_memories or not short_term_memories.short_term_memory_list:
                        break
                    stm_entities_and_preferences = []
                    stm_uuids = []
                    last_message_time = None
                    for memory in short_term_memories.short_term_memory_list:
                        stm_entities_and_preferences.append({
                            "profile": memory.profile,
                            "entities": memory.entities,
                            "preferences": memory.preferences,
                            "interests": memory.interests,
                        })
                        stm_uuids.append(memory.memory_uuid)
                        last_message_time = memory.message_time

                    if new_ltm_data:
                        ltm_entities_and_preferences = {
                            "profile": new_ltm_data.get("profile", {}),
                            "interests": new_ltm_data.get("interests", []),
                            "preferences": new_ltm_data.get("preferences", []),
                            # "needs": new_ltm_data.get("needs", []),
                        }
                    else:
                        ltm_entities_and_preferences = {
                            "profile": last_memory.profile if last_memory else {},
                            "interests": last_memory.interests if last_memory else [],
                            "preferences": last_memory.preferences if last_memory else [],
                            # "needs": last_memory.needs if last_memory else [],
                        }
                    new_ltm = self._extract_stm_to_ltm(ltm_entities_and_preferences, stm_entities_and_preferences)

                    # TODO resolve conflict between current preferences and history preferences

                    ltm_version_id = pendulum.now("UTC").strftime('%Y-%m-%dT%H:%M:%S') + f".{page_number:03d}"
                    new_ltm_data = {
                        "user_uuid": user_id,
                        "ltm_version_id": ltm_version_id,
                        "profile": new_ltm.get("profile", {}),
                        "interests": new_ltm.get("interests", []),
                        "preferences": new_ltm.get("preferences", []),
                        "needs": new_ltm.get("needs", []),
                        "create_log": new_ltm.get("metadata", {}),
                        "last_stm_time": last_message_time,
                    }
                    insert_update_long_term_memory(
                        self.info,
                        **new_ltm_data
                    )
                    for stm_uuid in stm_uuids:
                        insert_update_short_term_memory(
                            self.info,
                            **{
                                "user_uuid": user_id,
                                "ltm_version_id": ltm_version_id,
                                "memory_uuid": stm_uuid,
                            }
                        )

                    # 3. Save data to Neo4j database
                    if new_ltm_data:
                        self._save_to_neo4j(new_ltm_data)

                    if (short_term_memories.total + page_limit - 1) // page_limit <= page_number:
                        break
                    page_number += 1

            except Exception as e:
                print(e)
                self.logger.error(f"Failed to process user memory: {str(e)}")
                raise
        return True


    def get_long_term_memory(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get long term memory for user"""

        user_id = user_data.get("user_id")
        user_query = user_data.get("user_query", "")
        query_context = user_data.get("query_context", {})

        memory_result = {
            "user_uuid": user_id,
            "profile": {},
            "interests": [],
            "preferences": [],
        }

        # Get long term memory from database
        # ltm_list = resolve_long_term_memory_list(
        #     self.info,
        #     **{
        #         "user_uuid": user_id,
        #         "limit": 1,
        #     }
        # )
        # last_memory = ltm_list.long_term_memory_list[0] if ltm_list and ltm_list.long_term_memory_list else None
        # print(f"last_memory: {last_memory}")

        # cypher_query = f"""
        # MATCH (u:User {{user_uuid: "{user_id}"}})-[r:INTERESTS]->(i:InterestEntity)
        # OPTIONAL MATCH (u)-[r2:PREFERS]->(p:PreferenceEntity)
        # RETURN u, r, i, r2, p
        # """
        user_cypher_query = f"""
        MATCH (u:User {{user_uuid: "{user_id}"}})
        RETURN u
        LIMIT 1
        """
        profile = Config.graph_db_connector.driver.session().run(user_cypher_query).data()
        print(f"user_profile: {profile}")
        if not profile:
            return memory_result
        user_profile = profile[0].get("u", {}) if profile else {}
        user_profile.pop("user_uuid", None)
        ltm_version_id = user_profile.pop("ltm_version_id", None)

        preference_cypher_query = f"""
        MATCH (u:User {{user_uuid: "{user_id}"}})-[r:PREFERS]->(p:PreferenceEntity)
        RETURN p, properties(r) AS rp
        """
        preferences = Config.graph_db_connector.driver.session().run(preference_cypher_query).data()
        print(f"preferences: {preferences}")
        user_preferences = []
        for p in preferences:
            p["p"].update(p["rp"])
            user_preferences.append(p.get("p", {}))

        interest_cypher_query = f"""
        MATCH (u:User {{user_uuid: "{user_id}"}})-[r:INTERESTS]->(i:InterestEntity)
        RETURN i, properties(r) AS rp
        """
        interests = Config.graph_db_connector.driver.session().run(interest_cypher_query).data()
        print(f"interests: {interests}")
        user_interests = []
        for i in interests:
            i["i"].update(i["rp"])
            user_interests.append(i.get("i", {}))

        return {
            "user_uuid": user_id,
            "profile": user_profile,
            "interests": user_interests,
            "preferences": user_preferences,
        }



    def _extract_entities_and_perferences(self, user_query: str, episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract entity information and relationships"""

        system_prompt = self._get_entity_extraction_system_prompt()
        
        # Build user prompt
        user_prompt = self._build_entity_extraction_prompt(user_query, episodes)

        # Use large model to extract entities and relationships
        if Config.proxy_large_model:
            result = Config.proxy_large_model.provider.base_query(
                user_prompt, system_prompt, format="json"
            )
            return result
        else:
            # If large model is not available, use default implementation
            return self._default_entity_extraction(user_data)


    def _extract_stm_to_ltm(self, ltm_entities_and_preferences: Dict[str, Any], stm_entities_and_preferences: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract entity information and relationships"""

        system_prompt = self._get_stm_to_ltm_system_prompt()

        user_prompt = self._build_stm_to_ltm_user_prompt(stm_entities_and_preferences, ltm_entities_and_preferences)

        # Use large model to extract entities and relationships
        if Config.proxy_large_model:
            result = Config.proxy_large_model.provider.base_query(
                user_prompt, system_prompt, format="json"
            )
            print(f"-------_merge_stm_to_ltm------------\n: {result}\n------------------")
            return result


    def _save_to_neo4j(self, long_term_memory_data: Dict[str, Any]) -> None:

        try:
            # 创建Cypher查询
            ltm_version_id = long_term_memory_data.get("ltm_version_id")
            cypher_queries = self._build_cypher_queries(long_term_memory_data)
            
            # 执行查询
            if cypher_queries:
                for cypher_query in cypher_queries:
                    with Config.graph_db_connector.driver.session(
                        database=Config.graph_db_connector.database
                    ) as session:
                        session.run(cypher_query.get('query'), nodes = cypher_query.get('nodes'))

            self.logger.info(f"Long term memory data {ltm_version_id} saved to Neo4j")
            
        except Exception as e:
            self.logger.error(f"Failed to save long term memory data {ltm_version_id} to Neo4j: {str(e)}")
            raise


    def _build_cypher_queries(self, long_term_memory_data: Dict[str, Any]) -> List[str]:
        """Build Cypher queries"""
        
        cypher_statements = []
        user_uuid = long_term_memory_data.get("user_uuid")

        # Create or update user node
        user_cyphers = self._build_user_cypher(user_uuid, long_term_memory_data)
        print(f"--------user_cyphers\n: {user_cyphers}\n")
        cypher_statements.append(user_cyphers)

        # Create preference relationships
        if long_term_memory_data.get("preferences"):
            pref_queries = self._build_preference_cypher(user_uuid, long_term_memory_data.get("preferences"))
            cypher_statements.extend(pref_queries)

        # Create interest relationships
        if long_term_memory_data.get("interests"):
            interest_queries = self._build_interest_cypher(user_uuid, long_term_memory_data.get("interests"))
            cypher_statements.extend(interest_queries)
        
        return cypher_statements


    def _build_user_cypher(self, user_uuid: str, long_term_memory_data: Dict[str, Any]) -> str:
        """Build entity Cypher query"""
        ltm_version_id = long_term_memory_data.get("ltm_version_id")
        user_node = {
            "user_uuid": user_uuid,
            "ltm_version_id": ltm_version_id,
        }
        for profile_key, profile_value in long_term_memory_data.get("profile", {}).items():
            if profile_value:
                user_node[profile_key] = profile_value
        
        return self._build_nodes_cypher("User", "user_uuid", [user_node])


    def _build_preference_cypher(self, user_uuid: str, preferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build preference Cypher query"""

        # nodes: PreferenceCategory、PreferenceAttribute、PreferenceEntity
        # relationships: 
        # user->r:PREFERS->PreferenceEntity
        # PreferenceCategory->r:HAS_ATTRIBUTE->PreferenceAttribute、
        # PreferenceAttribute->r:VALUES->PreferenceEntity
        preference_cyphers = []
        category_nodes = {}
        category_attributes = {}
        preference_entities = {}
        category_attr_relates = []
        attr_value_relates = []
        user_pref_relates = []

        for preference in preferences:
            type = preference.get("category", "")
            sub_category = preference.get("sub_category", "")
            category_key = md5_string(type + "_" + sub_category)
            if category_key not in category_nodes:
                category_nodes[category_key] = {
                    "key": category_key,
                    "name": sub_category,
                    "type": type,
                }

            attribute = preference.get("attr_key", "")
            attribute_key = md5_string(type + "_" + sub_category + "_" + attribute)
            if attribute_key not in category_attributes:
                category_attributes[attribute_key] = {
                    "key": attribute_key,
                    "name": attribute,
                    "category": sub_category,
                    "type": type,
                }
                category_attr_relates.append({
                    "from_label": "PreferenceCategory",
                    "from_field": "key",
                    "from_field_val": category_key,
                    "to_label": "PreferenceAttribute",
                    "to_field": "key",
                    "to_field_val": attribute_key,
                    "rel_type": "HAS_ATTRIBUTE",
                })

            entity = preference.get("attr_value", "")
            entity_key = md5_string(type + "_" + sub_category + "_" + attribute + "_" + entity)
            if entity_key not in preference_entities:
                preference_entities[entity_key] = {
                    "key": entity_key,
                    "name": entity,
                    "category": sub_category,
                    "type": type,
                    "attr_key": attribute,
                }

                attr_value_relates.append({
                    "from_label": "PreferenceAttribute",
                    "from_field": "key",
                    "from_field_val": attribute_key,
                    "to_label": "PreferenceEntity",
                    "to_field": "key",
                    "to_field_val": entity_key,
                    "rel_type": "VALUES",
                })

                user_pref_relates.append({
                    "from_label": "User",
                    "from_field": "user_uuid",
                    "from_field_val": user_uuid,
                    "to_label": "PreferenceEntity",
                    "to_field": "key",
                    "to_field_val": entity_key,
                    "rel_type": "PREFERS",
                    "properties": {
                        "confidence": preference.get("confidence", 0.5),
                        "strength": preference.get("strength", ""),
                    }
                })
        if category_nodes:
            preference_cyphers.append(self._build_nodes_cypher("PreferenceCategory", "key", list(category_nodes.values())))
        
        if category_attributes:
            preference_cyphers.append(self._build_nodes_cypher("PreferenceAttribute", "key", list(category_attributes.values())))
        
        if preference_entities:
            preference_cyphers.append(self._build_nodes_cypher("PreferenceEntity", "key", list(preference_entities.values())))
        
        if category_attr_relates:
            for category_attr_relate in category_attr_relates:
                preference_cyphers.append(self._build_relationship_cypher(category_attr_relate))
        
        if attr_value_relates:
            for attr_value_relate in attr_value_relates:
                preference_cyphers.append(self._build_relationship_cypher(attr_value_relate))
        
        if user_pref_relates:
            for user_pref_relate in user_pref_relates:
                preference_cyphers.append(self._build_relationship_cypher(user_pref_relate))

        print(f"--------preference_cyphers\n: {preference_cyphers}\n")
        return preference_cyphers

        # return f"""
        # MATCH (u:User {{user_id: "{user_id}"}})
        # MERGE (c:Category {{name: "{category}"}})
        # MERGE (u)-[p:PREFERS]->(c)
        # SET p.preference_level = "{preference_level}",
        #     p.confidence = {confidence},
        #     p.valid_at = "{current_time}",
        #     p.invalid_at = null,
        #     p.group_id = "user_media_preferences"
        # """


    def _build_interest_cypher(self, user_uuid: str, interests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build interest Cypher query"""

        # Labels: InterestCategory、InterestEntity
        # relationships: 
        # user->r:PREFERS->InterestEntity
        # InterestCategory->r:RELATES_TO->InterestEntity
        interest_cyphers = []
        category_nodes = {}
        interest_entities = {}
        category_entity_relates = []
        user_interest_relates = []
        interest_relates = []
        for interest in interests:
            type = interest.get("category", "") 
            sub_category = interest.get("sub_category", "")
            category_key = md5_string(type + "_" + sub_category)
            if category_key not in category_nodes:
                category_nodes[category_key] = {
                    "key": category_key,
                    "name": sub_category,
                    "type": type,
                }

            entity = interest.get("name", "")
            entity_key = md5_string(type + "_" + sub_category + "_" + entity)
            if entity_key not in interest_entities:
                interest_entities[entity_key] = {
                    "key": entity_key,
                    "name": entity,
                    "category": sub_category,
                    "type": type,
                }

                category_entity_relates.append({
                    "from_label": "InterestCategory",
                    "from_field": "key",
                    "from_field_val": category_key,
                    "to_label": "InterestEntity",
                    "to_field": "key",
                    "to_field_val": entity_key,
                    "rel_type": "RELATES_TO",
                })

                user_interest_relates.append({
                    "from_label": "User",
                    "from_field": "user_uuid",
                    "from_field_val": user_uuid,
                    "to_label": "InterestEntity",
                    "to_field": "key",
                    "to_field_val": entity_key,
                    "rel_type": "INTERESTS",
                    "properties": {
                        "confidence": interest.get("confidence", 0.5),
                        "strength": interest.get("strength", ""),
                    }
                })

        if category_nodes:
            interest_cyphers.append(self._build_nodes_cypher("InterestCategory", "key", list(category_nodes.values())))

        if interest_entities:
            interest_cyphers.append(self._build_nodes_cypher("InterestEntity", "key", list(interest_entities.values())))

        if category_entity_relates:
            for category_entity_relate in category_entity_relates:
                interest_cyphers.append(self._build_relationship_cypher(category_entity_relate))
        
        if user_interest_relates:
            for user_interest_relate in user_interest_relates:
                interest_cyphers.append(self._build_relationship_cypher(user_interest_relate))
        return interest_cyphers


    def _build_nodes_cypher(self, label: str, primary_key: str, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build nodes Cypher query"""

        query = """
        UNWIND $nodes AS node 
        MERGE (n:%s {%s: node.%s}) 
        ON CREATE SET n = node 
        ON MATCH SET n += node
        """ % (label, primary_key, primary_key)
        return {
            "query": query,
            "nodes": nodes
        }


    def _build_relationship_cypher(self, relationship: Dict[str, Any]) -> str:
        """Build relationship Cypher query"""
        
        from_label = relationship.get("from_label")
        from_field = relationship.get("from_field")
        from_field_val = relationship.get("from_field_val")
        to_label = relationship.get("to_label")
        to_field = relationship.get("to_field")
        to_field_val = relationship.get("to_field_val")
        rel_type = relationship.get("rel_type", "RELATES_TO")
        properties = relationship.get("properties", {})
        
        props_str = ", ".join([f"r.{k} = \"{v}\"" for k, v in properties.items()])
        
        query = f"""
        MATCH (a:{from_label} {{{from_field}: "{from_field_val}"}}), (b:{to_label} {{{to_field}: "{to_field_val}"}})
        MERGE (a)-[r:{rel_type}]->(b)
        """
        if props_str:
            query += f"\nSET {props_str}"

        return {
            "query": query,
            "nodes": []
        }


    def _build_response(self, user_data: Dict[str, Any],
                       entities: List[Dict[str, Any]],
                       preferences: List[Dict[str, Any]],
                       interests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build response data structure"""

        # Build edge relationships
        return {
            "user_id": user_data.get("user_id"),
            "edges": entities,
            "preferences": preferences,
            "interests": interests
        }


    def _build_entity_extraction_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build prompt for entity extraction."""
        context_section = f"\n\nContext from previous analysis: {context}" if context else ""

        prompt = f"""Analyze the following user context text and extract behavior entities.

Text to analyze:
{text}

{context_section}
"""
        return prompt


    def _get_entity_extraction_system_prompt(self) -> str:
        """Get system prompt for entity extraction."""
        # prompt template backup
        """
        Please extract the following types of entities:
        - Products mentioned or interacted with
        - Services used or discussed
        - Content consumed (articles, videos, etc.)
        - Actions performed (purchases, clicks, views, etc.)
        - Interactions with systems or people
        - Explicit preferences stated
        - Behaviors exhibited
        - Topics of interest
        - Categories of content/products

        For each entity, provide:
        1. name: The entity name/title
        2. type: One of: product, service, content, action, interaction, preference, behavior, interest, topic, category
        3. description: Brief description of the entity
        4. confidence: Confidence score (0.0-1.0)
        5. sentiment: Sentiment towards this entity (positive, negative, neutral)
        6. frequency: How often mentioned (1-5 scale)
        """

        return """Please extract the following types of entities and infer preferences, interests from user context text:
- Products mentioned or interacted with
- Services used or discussed
- Explicit preferences stated
- Topics of interest
- Industry categories (e.g., technology, finance, healthcare)

For each entity, provide:
1. name: The entity name/title
2. type: One of: product, service, topic, industry
3. description: Brief description of the entity
4. confidence: Confidence score (0.0-1.0)
5. sentiment: Sentiment towards this entity (positive, negative, neutral)
6. frequency: How often mentioned (1-5 scale)
7. category: The category of the entity (e.g., movie, book, product category, industry category)
8. evidence: Supporting evidence from the text (e.g., quotes, statements, references)

Preference emphasis refers to users' choice tendencies and behavioral habits towards things.
For each preference provide:
1. category: Type of preference (consumption/living_habits)
2. sub_category: Specific category within the preference type (e.g., shopping, sport)
3. attr_key: Specific preference attribute key by the sub_category (e.g., brand, time, ...)
3. attr_value: Specific preference attribute name by the attr_key (e.g., nike, afternoon, ...)
4. confidence: Confidence score (0.0-1.0)
5. evidence: Supporting evidence from entities
6. strength: Preference strength (weak, moderate, strong)

Interest orientation refers to a user's attention and willingness to explore a certain field.
For each interest provide:
1. category: Type of interest (professional/hobby/academic)
2. sub_category: Specific category within the interest type (e.g., technology, sport, ...)
3. name: Specific interest name by the sub_category (e.g., battery production, basketball, ...)
4. confidence: Confidence score (0.0-1.0)
5. evidence: Supporting evidence from entities
6. strength: Interest strength (weak, moderate, strong)

Profile contains the following attributes if provided:
- gender: "male/female/non-binary"
- age_range: "e.g., 25-34"
- occupation: "profession"
- education_level: "highest education"
- location: "geographic area"
- language_preference: "primary language"
- communication_style: "technical/casual/formal"

Output requirements (strictly JSON format, don't include any other text):
{{
    "profile": {...},
    "entities": [
        ...
    ],
    "preferences": [
        ...
    ],
    "interests": [
        ...
    ],
}}"""



    def _build_preference_inference_prompt(self, entities_json: str, context: Optional[str] = None) -> str:
        """Build prompt for preference inference."""
        context_section = f"\n\nContext from previous analysis: {context}" if context else ""
        
        prompt = f"""Based on the following extracted entities, infer user preferences and behavioral patterns.

Extracted Entities:
{entities_json}

{context_section}

Please infer:
1. Product preferences (brands, features, price ranges)
2. Content preferences (topics, formats, sources)
3. Behavioral preferences (timing, frequency, methods)
4. Topic interests (subjects user is interested in)
5. Style preferences (communication, visual, interaction styles)
6. Timing preferences (when user prefers to engage)

For each preference, provide:
1. category: Type of preference
2. value: The preference value/description
3. confidence: Confidence score (0.0-1.0)
4. evidence: Supporting evidence from entities
5. strength: Preference strength (weak, moderate, strong)

Return the results in JSON format with a list of preferences under key "preferences"."""
        
        return prompt


    def _get_preference_inference_system_prompt(self) -> str:
        """Get system prompt for preference inference."""
        return """You are an expert at inferring user preferences from behavioral entities.
You analyze patterns in user behavior to identify preferences, interests, and tendencies.
You provide well-reasoned inferences with confidence scores and supporting evidence.
You focus on preferences that are actionable for personalization and recommendation systems."""




    def _build_stm_to_ltm_user_prompt(self, stm_entities_and_preferences: Optional[Dict[str, Any]], ltm_entities_and_preferences: Optional[Dict[str, Any]] = None) -> str:
        """Build prompt for preference inference."""

        prompt = f"""
stm_entities_and_preferences:
{stm_entities_and_preferences}

long_term_memory:
{ltm_entities_and_preferences}
"""
        return prompt


    def _get_stm_to_ltm_system_prompt(self) -> str:
        """Get system prompt for short-term memory to long-term memory transformation."""
#         return """You are a memory integration expert specializing in consolidating user-specific entities and preferences from short-term memory (STM) into long-term memory (LTM). Your core tasks are: 1) Extract and normalize structured entities/preferences from STM; 2) Align with existing LTM data; 3) Resolve conflicts logically; 4) Generate an updated LTM with clear audit trails.

# ### Input Data
# - Short-Term Memory (STM): {{stm_entities_and_preferences}}  // e.g., {"entities": [{"type": "technology", "value": "Kubernetes", "confidence": 0.95}, ...], "preferences": [{"domain": "cloud_native", "key": "deployment_tool", "value": "Helm", "timestamp": "2024-05-20T14:30:00"}]}
# - Long-Term Memory (LTM): {{ltm_entities_and_preferences}}  // e.g., {"entities": [{"type": "technology", "value": "Docker", "confidence": 0.88, "last_updated": "2024-03-15T09:10:00"}], "preferences": [{"domain": "cloud_native", "key": "deployment_tool", "value": "Kustomize", "timestamp": "2024-02-01T11:20:00", "is_default": false}]}

# ### Step-by-Step Instructions
# 1. **Extract & Normalize STM Data**
#    - Identify all entities (e.g., technologies, tools, concepts) and preferences (e.g., domain-specific choices, behavior patterns) from STM.
#    - Standardize formats: 
#      - Entities: {type: string, value: string, confidence: float (0-1), source: "STM", timestamp: string}
#      - Preferences: {domain: string, key: string, value: string/boolean/number, timestamp: string, source: "STM"}

# 2. **Align with LTM Data**
#    - For each STM entity:
#      - Check if LTM has an entity with the same `type` and matching `value` (fuzzy match allowed for synonyms, e.g., "K8s" ≈ "Kubernetes").
#      - If match exists: Flag as "duplicate" (for consolidation) or "conflict" (if core attributes differ).
#      - If no match: Flag as "new entity" (to be added to LTM).
#    - For each STM preference:
#      - Check if LTM has a preference with the same `domain` and `key`.
#      - If match exists: Compare `value`; flag as "consistent" (values match) or "conflict" (values differ).
#      - If no match: Flag as "new preference" (to be added to LTM).

# 3. **Conflict Resolution Rules**
#    - **Entity Conflicts**:
#      - Higher confidence (STM > LTM by ≥0.1): Replace LTM entity with STM entity; retain LTM `last_updated` as STM timestamp.
#      - Lower confidence (STM < LTM by ≥0.1): Keep LTM entity; add STM entity as a "related entity" with a note.
#      - Confidence difference <0.1: Merge attributes (e.g., average confidence); mark as "merged entity".
#    - **Preference Conflicts**:
#      - Recency (STM timestamp > LTM timestamp): Override LTM value with STM value; update `last_updated` to STM timestamp.
#      - LTM `is_default: true`: Keep LTM value unless STM has explicit user confirmation (e.g., "I prefer Helm instead of Kustomize"); if confirmed, set `is_default: false` in LTM and add STM preference as primary.
#      - Ambiguous conflicts (e.g., same timestamp, no confidence score): Preserve both values as "alternative preferences" with a conflict note (e.g., "User has conflicting preferences for deployment_tool: Kustomize (2024-02-01) and Helm (2024-05-20)").

# 4. **Generate Updated LTM**
#    - Structure the final LTM with:
#      - Merged/added entities (retaining all normalized fields + `last_updated` timestamp).
#      - Resolved/preferred preferences (with `is_default` flag if applicable).
#      - Conflict log: List all unresolved conflicts with timestamps, sources, and resolution rationale.
#      - Audit trail: Track all changes (e.g., "Replaced LTM entity Docker with STM entity Kubernetes (higher confidence: 0.95 > 0.88)").

# ### Output Format (strictly JSON format, don't include any other text)
# {
#   "updated_ltm": {
#     "entities": [...],  // Normalized entities after merging/conflict resolution
#     "preferences": [...]  // Resolved preferences after merging/conflict resolution
#   },
#   "conflict_log": [
#     {
#       "conflict_type": "entity/preference",
#       "stm_entry": {...},
#       "ltm_entry": {...},
#       "resolution": "replaced/merged/kept_both/unresolved",
#       "rationale": "string explaining the resolution"
#     }
#   ],
#   "audit_trail": ["string describing each change made to LTM"]
# }

# ### Constraints
# - Preserve high-confidence LTM data unless STM provides stronger evidence (higher confidence/recency/explicit confirmation).
# - Use synonym mapping for technical terms (e.g., "distributed transactions" ≈ "DTMs", "TensorFlow" ≈ "TF") to avoid false conflicts.
# - Maintain data consistency: Ensure entity types and preference domains/keys follow LTM schema (if LTM has a defined schema; if not, infer from existing entries).
# - Avoid overwriting critical LTM data (e.g., user core preferences marked as "permanent") without explicit STM confirmation."""


#   "needs": [
#     {
#       "type": "short_term/long_term/ongoing",
#       "category": "skill_development/problem_solving/information/emotional",
#       "description": "need/goal statement",
#       "priority": "low/medium/high/critical",
#       "progress": "not_started/in_progress/partially_completed/completed",
#       "timeframe": "completion estimate",
#       "related_interests": ["linked interest names"]
#       "operation": "add/merge/decay"
#     }
#   ]

        return """System Prompt: Long-term Memory Extraction & Consolidation

Role: Long-term Memory Processor for AI conversational system. Extract patterns from user interactions and maintain evolving memory profile.

Core Tasks:
1. Consolidate short-term memory (recent entities/preferences):{{stm_entities_and_preferences}} with existing long-term memory:{{long_term_memory}}
2. Resolve conflicts between new and existing information
3. Identify stable preferences, behaviors, and interests
4. Maintain accurate, current user profile

Processing Rules:
- Analyze recent interactions: mentioned entities, expressed preferences, implicit behaviors
- Compare with existing long-term memory
- Merge: -Reinforce: Increase confidence when new evidence supports existing items
- Merge: -Resolve conflicts: Favor recent info unless contradicted by multiple past instances
- Add: add new items, Minimum 2-3 consistent mentions/behaviors required
- Decay: Reduce confidence for items not reinforced over time

Preference emphasis refers to users' choice tendencies and behavioral habits towards things.
For each preference provide:
1. category: Type of preference (consumption/living_habits)
2. sub_category: Specific category within the preference type (e.g., shopping, sport)
3. attr_key: Specific preference attribute key by the sub_category (e.g., brand, time, ...)
3. attr_value: Specific preference attribute name by the attr_key (e.g., nike, afternoon, ...)
4. confidence: Confidence score (0.0-1.0)
5. evidence: Supporting evidence from entities
6. strength: Preference strength (weak, moderate, strong)
7. "operation": "add/merge/decay"

Interest orientation refers to a user's attention and willingness to explore a certain field.
For each interest provide:
1. category: Type of interest (professional/hobby/academic)
2. sub_category: Specific category within the interest type (e.g., technology, sport, ...)
3. name: Specific interest name by the sub_category (e.g., battery production, basketball, ...)
4. confidence: Confidence score (0.0-1.0)
5. evidence: Supporting evidence from entities
6. strength: Interest strength (weak, moderate, strong)
7. "operation": "add/merge/decay"

Memory Structure (Output JSON only):
{
  "profile": {
    ...
  },
  "preferences": [
    ...
  ],
  "interests": [
    ...
  ],
  "metadata": {
    ...
  }
}

Evidence Standards:
- Strong (≥0.8): Direct statements, repeated mentions, consistent patterns
- Moderate (0.5-0.7): Indirect mentions, single strong instances, logical inferences
- Weak (≤0.4): Isolated mentions, ambiguous statements, unverified inferences

Output Requirements:
- Return ONLY valid JSON matching above structure
- Include metadata: memory_updates, confidence_changes, conflicts_resolved, timestamp
- Document evidence for each item
- Explain conflict resolutions

Special Instructions:
1. Privacy: Never infer sensitive attributes without explicit consent
2. Cultural awareness: Consider cultural context
3. Temporal dynamics: Allow for legitimate preference changes
4. Confidence calibration: Be conservative; require strong evidence for high confidence
5. JSON validation: Ensure exact schema compliance
6. Conflict transparency: Document reasoning for resolutions

Quality Guidelines:
- Accuracy over completeness
- Consider conversation context
- Allow for user evolution
- Check internal consistency
- Maintain evidence chain"""