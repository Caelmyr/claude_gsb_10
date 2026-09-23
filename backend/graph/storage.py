"""
图谱存储模块 - JSON文件分片存储
"""
import json
import os
import threading
from typing import Dict, List, Optional
from backend.utils.config import GRAPH_DIR, GRAPH_SHARDS

# 人工标注/无文档来源的计数键，不随文档删除而回收
MANUAL_SOURCE = '__manual__'


class GraphStorage:
    """图谱存储管理器 - 按实体类型分片"""

    def __init__(self):
        # 使用可重入锁：add_relation 内部会调用 add_entity
        self.lock = threading.RLock()
        self._ensure_directories()
        self._cache = {}
        self._load_all_shards()

    def _ensure_directories(self):
        """确保目录存在"""
        os.makedirs(GRAPH_DIR, exist_ok=True)

    def _load_all_shards(self):
        """加载所有分片到缓存"""
        for entity_type, filename in GRAPH_SHARDS.items():
            filepath = os.path.join(GRAPH_DIR, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    shard = json.load(f)
            else:
                shard = {'entities': {}, 'relations': []}
            self._cache[entity_type] = self._normalize_shard(shard)

    def _normalize_shard(self, shard: Dict) -> Dict:
        """规范化分片数据，补齐来源追踪字段（兼容历史数据）"""
        for entity_text, entity in shard.get('entities', {}).items():
            if 'sources' not in entity:
                # 历史数据：人工标注归入人工来源（删除文档不回收）；
                # 其余按 properties 中的 doc_id 归入对应文档来源
                props = entity.get('properties') or {}
                if props.get('manual'):
                    entity['sources'] = {MANUAL_SOURCE: entity.get('count', 1)}
                elif props.get('doc_id'):
                    entity['sources'] = {props['doc_id']: entity.get('count', 1)}
                else:
                    entity['sources'] = {MANUAL_SOURCE: entity.get('count', 1)}
            entity['count'] = self._compute_count(entity['sources'])

        for relation in shard.get('relations', []):
            props = relation.get('properties') or {}
            if 'source_docs' not in relation:
                is_manual = bool(props.get('manual'))
                relation['source_docs'] = [] if is_manual or not props.get('doc_id') \
                    else [props['doc_id']]
            if 'manual' not in relation:
                relation['manual'] = bool(props.get('manual'))

        return shard

    @staticmethod
    def _compute_count(sources: Dict[str, int]) -> int:
        """根据来源计数汇总实体出现次数"""
        return sum(sources.values())

    def _save_shard(self, entity_type: str):
        """保存指定分片到文件"""
        filename = GRAPH_SHARDS.get(entity_type, 'other.json')
        filepath = os.path.join(GRAPH_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._cache[entity_type], f, ensure_ascii=False, indent=2)

    def add_entity(self, entity_text: str, entity_type: str, properties: Dict = None):
        """添加实体

        properties 可携带:
          - doc_id: 来源文档ID，按文档登记出现次数，文档删除时回收
          - manual: 人工标注，计入人工来源，不随文档删除
        """
        with self.lock:
            if entity_type not in self._cache:
                self._cache[entity_type] = {'entities': {}, 'relations': []}

            properties = properties or {}
            doc_id = properties.get('doc_id')
            # 人工标注优先归入人工来源，不随任何文档删除而回收
            source_key = MANUAL_SOURCE if properties.get('manual') else (doc_id or MANUAL_SOURCE)

            entities = self._cache[entity_type]['entities']
            if entity_text not in entities:
                entities[entity_text] = {
                    'id': f"{entity_type}_{len(entities)}",
                    'text': entity_text,
                    'type': entity_type,
                    'properties': properties,
                    'sources': {source_key: 1}
                }
            else:
                entity = entities[entity_text]
                entity.setdefault('sources', {})
                entity['sources'][source_key] = entity['sources'].get(source_key, 0) + 1
                # 保留上下文中的补充信息
                if properties.get('context') and not entity['properties'].get('context'):
                    entity['properties']['context'] = properties['context']

            entities[entity_text]['count'] = self._compute_count(entities[entity_text]['sources'])
            self._save_shard(entity_type)

    def add_relation(self, subject: str, subject_type: str, predicate: str,
                     obj: str, object_type: str, properties: Dict = None):
        """添加关系"""
        with self.lock:
            properties = properties or {}
            doc_id = properties.get('doc_id')
            is_manual = bool(properties.get('manual'))
            # 人工标注的关系/实体归入人工来源，不随文档删除而回收
            relation_doc_id = None if is_manual else doc_id

            # 确保实体存在，并把文档来源传递给端点实体
            endpoint_props = {'doc_id': relation_doc_id} if relation_doc_id else {}
            if is_manual:
                endpoint_props['manual'] = True
            self.add_entity(subject, subject_type, endpoint_props)
            self.add_entity(obj, object_type, endpoint_props)

            # 添加关系到主语所在分片
            if subject_type not in self._cache:
                self._cache[subject_type] = {'entities': {}, 'relations': []}

            relation = {
                'subject': subject,
                'subject_type': subject_type,
                'predicate': predicate,
                'object': obj,
                'object_type': object_type,
                'properties': properties,
                'source_docs': [doc_id] if relation_doc_id else [],
                'manual': is_manual
            }

            # 检查是否已存在：存在则合并来源文档
            existing = self._cache[subject_type]['relations']
            for r in existing:
                if r['subject'] == subject and r['predicate'] == predicate and r['object'] == obj:
                    r.setdefault('source_docs', [])
                    if doc_id and doc_id not in r['source_docs']:
                        r['source_docs'].append(doc_id)
                    r['manual'] = r.get('manual', False) or is_manual
                    self._save_shard(subject_type)
                    return

            existing.append(relation)
            self._save_shard(subject_type)

    def remove_document_data(self, doc_id: str) -> Dict:
        """删除指定文档产生的全部图谱数据（实体、关系）

        - 实体按来源文档计数回收；仍被其他文档或人工标注引用的实体保留
        - 关系从 source_docs 中移除该文档；无任何来源且非人工标注的关系删除
        - 最后清理端点实体已不存在的悬空关系
        """
        removed_entities = 0
        removed_relations = 0

        with self.lock:
            for entity_type, shard in self._cache.items():
                # 1. 回收实体
                entities = shard['entities']
                for entity_text in list(entities.keys()):
                    entity = entities[entity_text]
                    sources = entity.setdefault('sources', {})
                    if doc_id in sources:
                        del sources[doc_id]
                    if sources:
                        entity['count'] = self._compute_count(sources)
                    else:
                        del entities[entity_text]
                        removed_entities += 1

                # 2. 回收关系
                relations = shard['relations']
                kept = []
                for relation in relations:
                    source_docs = relation.setdefault('source_docs', [])
                    if doc_id in source_docs:
                        relation['source_docs'] = [d for d in source_docs if d != doc_id]
                    if relation['source_docs'] or relation.get('manual'):
                        kept.append(relation)
                    else:
                        removed_relations += 1
                shard['relations'] = kept

            # 3. 清理端点实体已不存在的悬空关系
            removed_relations += self._remove_dangling_relations()

            # 4. 持久化所有分片
            for entity_type in self._cache:
                self._save_shard(entity_type)

        return {
            'doc_id': doc_id,
            'removed_entities': removed_entities,
            'removed_relations': removed_relations
        }

    def _remove_dangling_relations(self) -> int:
        """删除端点实体已不存在的悬空关系，返回删除数量"""
        removed = 0
        for shard in self._cache.values():
            before = len(shard['relations'])
            shard['relations'] = [
                r for r in shard['relations']
                if self.get_entity(r['subject']) and self.get_entity(r['object'])
            ]
            removed += before - len(shard['relations'])
        return removed

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
