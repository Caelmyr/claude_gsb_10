"""
图谱存储模块 - JSON文件分片存储

实体和关系通过 doc_ids 记录其来源文档，删除文档时可据此做级联清理：
- 实体被多个文档共享时，只移除对应来源，不删除实体；
- 仅当实体不再来自任何文档、且没有剩余关系引用时才真正删除；
- 手动标注（properties.manual=True）的数据不随文档删除。
"""
import json
import os
import threading
from typing import Dict, List, Optional
from backend.utils.config import GRAPH_DIR, GRAPH_SHARDS


class GraphStorage:
    """图谱存储管理器 - 按实体类型分片"""

    def __init__(self):
        self.lock = threading.RLock()
        self._ensure_directories()
        self._cache = {}
        self._load_all_shards()

    def _ensure_directories(self):
        """确保目录存在"""
        os.makedirs(GRAPH_DIR, exist_ok=True)

    def _load_all_shards(self):
        """加载所有分片到缓存，并兼容旧数据结构"""
        for entity_type, filename in GRAPH_SHARDS.items():
            filepath = os.path.join(GRAPH_DIR, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    shard = json.load(f)
            else:
                shard = {'entities': {}, 'relations': []}

            shard.setdefault('entities', {})
            shard.setdefault('relations', [])
            self._migrate_shard(entity_type, shard)
            self._cache[entity_type] = shard

    def _migrate_shard(self, entity_type: str, shard: Dict):
        """补全新增字段（doc_ids / next_id），兼容历史分片文件"""
        max_id = -1
        for entity_text, entity in shard['entities'].items():
            # 旧数据没有 doc_ids，从 properties.doc_id 回填
            if 'doc_ids' not in entity:
                legacy_doc_id = entity.get('properties', {}).get('doc_id')
                entity['doc_ids'] = [legacy_doc_id] if legacy_doc_id else []
            entity.setdefault('count', len(entity['doc_ids']) or 1)
            entity.setdefault('properties', {})
            max_id = max(max_id, self._parse_id_suffix(entity.get('id', '')))

        for relation in shard['relations']:
            if 'doc_ids' not in relation:
                legacy_doc_id = relation.get('properties', {}).get('doc_id')
                relation['doc_ids'] = [legacy_doc_id] if legacy_doc_id else []

        shard['next_id'] = max(shard.get('next_id', 0), max_id + 1)

    @staticmethod
    def _parse_id_suffix(entity_id: str) -> int:
        """解析实体id末尾的数字序号"""
        if not entity_id or '_' not in entity_id:
            return -1
        try:
            return int(entity_id.rsplit('_', 1)[1])
        except ValueError:
            return -1

    def _new_entity_id(self, entity_type: str) -> str:
        """在分片内生成稳定且唯一的实体id（不随删除回收）"""
        shard = self._cache[entity_type]
        next_id = shard.get('next_id', 0)
        shard['next_id'] = next_id + 1
        return f"{entity_type}_{next_id}"

    def _save_shard(self, entity_type: str):
        """保存指定分片到文件"""
        filename = GRAPH_SHARDS.get(entity_type, 'other.json')
        filepath = os.path.join(GRAPH_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._cache[entity_type], f, ensure_ascii=False, indent=2)

    @staticmethod
    def _is_manual(data: Dict) -> bool:
        """是否为手动标注的数据（不随文档删除）"""
        return bool(data.get('properties', {}).get('manual'))

    def add_entity(self, entity_text: str, entity_type: str,
                   properties: Dict = None, doc_id: str = None) -> Dict:
        """添加实体

        同一实体在同一文档内重复添加不会累加计数；被新文档引入时才增加来源。
        """
        with self.lock:
            if entity_type not in self._cache:
                self._cache[entity_type] = {
                    'entities': {}, 'relations': [], 'next_id': 0
                }

            entities = self._cache[entity_type]['entities']
            entity = entities.get(entity_text)

            if entity is None:
                entity = {
                    'id': self._new_entity_id(entity_type),
                    'text': entity_text,
                    'type': entity_type,
                    'properties': dict(properties or {}),
                    'doc_ids': [doc_id] if doc_id else [],
                    'count': 1
                }
                entities[entity_text] = entity
            else:
                if doc_id and doc_id not in entity['doc_ids']:
                    entity['doc_ids'].append(doc_id)
                    entity['count'] = len(entity['doc_ids'])
                if properties:
                    entity['properties'].update(properties)

            self._save_shard(entity_type)
            return entity

    def _ensure_entity(self, entity_text: str, entity_type: str):
        """确保关系两端的实体存在，不重复累加已有实体的计数（调用方负责保存分片）"""
        if entity_type not in self._cache:
            self._cache[entity_type] = {
                'entities': {}, 'relations': [], 'next_id': 0
            }

        entities = self._cache[entity_type]['entities']
        if entity_text not in entities:
            entities[entity_text] = {
                'id': self._new_entity_id(entity_type),
                'text': entity_text,
                'type': entity_type,
                'properties': {},
                'doc_ids': [],
                'count': 1
            }

    def add_relation(self, subject: str, subject_type: str, predicate: str,
                     obj: str, object_type: str, properties: Dict = None,
                     doc_id: str = None) -> Dict:
        """添加关系（按 主语/谓语/宾语 去重，重复添加只补充文档来源）"""
        with self.lock:
            # 确保关系两端的实体存在（不重复增加实体计数）
            self._ensure_entity(subject, subject_type)
            self._ensure_entity(obj, object_type)

            if subject_type not in self._cache:
                self._cache[subject_type] = {
                    'entities': {}, 'relations': [], 'next_id': 0
                }

            relation = {
                'subject': subject,
                'subject_type': subject_type,
                'predicate': predicate,
                'object': obj,
                'object_type': object_type,
                'properties': properties or {},
                'doc_ids': [doc_id] if doc_id else []
            }

            existing_relations = self._cache[subject_type]['relations']
            existing = next(
                (r for r in existing_relations
                 if r['subject'] == subject and r['predicate'] == predicate
                 and r['object'] == obj),
                None
            )

            if existing is None:
                existing_relations.append(relation)
                result = relation
            else:
                if doc_id and doc_id not in existing['doc_ids']:
                    existing['doc_ids'].append(doc_id)
                if properties:
                    existing['properties'].update(properties)
                result = existing

            # 关系挂在主语分片，宾语实体可能落在另一个分片，两个分片都需落盘
            self._save_shard(subject_type)
            if object_type != subject_type:
                self._save_shard(object_type)
            return result

    def remove_document_data(self, doc_id: str) -> Dict:
        """删除某文档产生的全部图谱数据（实体、关系）

        - 关系：移除该文档来源；无任何剩余来源（且非手动标注）时删除关系；
        - 实体：移除该文档来源；无剩余来源、无剩余关系引用且非手动标注时删除；
        - 被其他文档或手动标注共享的数据会保留。
        """
        with self.lock:
            relations_removed = 0
            touched_shards = set()

            # 1. 先清理关系（所有分片都要扫描，关系按主语类型分片）
            for entity_type, shard in self._cache.items():
                remaining = []
                for relation in shard['relations']:
                    if doc_id in relation['doc_ids']:
                        relation['doc_ids'].remove(doc_id)
                        touched_shards.add(entity_type)
                    # 仍有文档来源，或属于手动标注（无文档来源），则保留
                    if relation['doc_ids'] or self._is_manual(relation):
                        remaining.append(relation)
                    else:
                        relations_removed += 1
                        touched_shards.add(entity_type)
                shard['relations'] = remaining

            # 2. 再清理实体：无剩余来源且不再被任何关系引用时才删除
            entities_removed = 0
            referenced = self._collect_referenced_entities()

            for entity_type, shard in self._cache.items():
                entities = shard['entities']
                for entity_text in list(entities.keys()):
                    entity = entities[entity_text]
                    if doc_id not in entity['doc_ids']:
                        continue

                    entity['doc_ids'].remove(doc_id)
                    touched_shards.add(entity_type)

                    if entity['doc_ids']:
                        # 仍被其他文档引用
                        entity['count'] = len(entity['doc_ids'])
                        continue

                    if self._is_manual(entity) or entity_text in referenced:
                        # 手动标注保留；仍被剩余关系引用的实体也保留，避免出现悬挂连线
                        entity['count'] = 1
                        continue

                    del entities[entity_text]
                    entities_removed += 1

            for entity_type in touched_shards:
                self._save_shard(entity_type)

            return {
                'entities_removed': entities_removed,
                'relations_removed': relations_removed
            }

    def _collect_referenced_entities(self) -> set:
        """收集当前被任意关系引用的实体文本"""
        referenced = set()
        for shard in self._cache.values():
            for relation in shard['relations']:
                referenced.add(relation['subject'])
                referenced.add(relation['object'])
        return referenced

    def get_entity(self, entity_text: str) -> Optional[Dict]:
        """获取实体信息"""
        for entity_type, shard in self._cache.items():
            if entity_text in shard['entities']:
                return shard['entities'][entity_text]
        return None

    def get_entity_relations(self, entity_text: str) -> List[Dict]:
        """获取实体的所有关系"""
        relations = []
        for entity_type, shard in self._cache.items():
            for relation in shard['relations']:
                if relation['subject'] == entity_text or relation['object'] == entity_text:
                    relations.append(relation)
        return relations

    def get_all_entities(self) -> List[Dict]:
        """获取所有实体"""
        entities = []
        for entity_type, shard in self._cache.items():
            entities.extend(shard['entities'].values())
        return entities

    def get_all_relations(self) -> List[Dict]:
        """获取所有关系"""
        relations = []
        for entity_type, shard in self._cache.items():
            relations.extend(shard['relations'])
        return relations

    def get_graph_data(self) -> Dict:
        """获取图谱可视化数据"""
        nodes = []
        links = []
        node_ids = set()

        for entity_type, shard in self._cache.items():
            for entity_text, entity_data in shard['entities'].items():
                if entity_data['id'] not in node_ids:
                    node_ids.add(entity_data['id'])
                    nodes.append({
                        'id': entity_data['id'],
                        'label': entity_text,
                        'type': entity_type,
                        'count': entity_data.get('count', 1)
                    })

            for relation in shard['relations']:
                source_entity = self.get_entity(relation['subject'])
                target_entity = self.get_entity(relation['object'])
                if source_entity and target_entity:
                    links.append({
                        'source': source_entity['id'],
                        'target': target_entity['id'],
                        'label': relation['predicate']
                    })

        return {'nodes': nodes, 'links': links}

    def search_entities(self, keyword: str) -> List[Dict]:
        """搜索实体"""
        results = []
        for entity_type, shard in self._cache.items():
            for entity_text, entity_data in shard['entities'].items():
                if keyword in entity_text:
                    results.append(entity_data)
        return results

    def get_statistics(self) -> Dict:
        """获取图谱统计信息"""
        total_entities = 0
        total_relations = 0
        entity_counts = {}

        for entity_type, shard in self._cache.items():
            count = len(shard['entities'])
            entity_counts[entity_type] = count
            total_entities += count
            total_relations += len(shard['relations'])

        return {
            'total_entities': total_entities,
            'total_relations': total_relations,
            'entity_counts': entity_counts
        }
