"""
图谱查询模块 - 支持多种查询方式
"""
from typing import List, Dict, Optional
from backend.graph.storage import GraphStorage


class GraphQuery:
    """图谱查询引擎"""

    def __init__(self, storage: GraphStorage):
        self.storage = storage

    def query_entity(self, entity_text: str) -> Dict:
        """查询单个实体及其关系"""
        entity = self.storage.get_entity(entity_text)
        if not entity:
            return {'found': False, 'entity': None, 'relations': []}

        relations = self.storage.get_entity_relations(entity_text)

        # 构建关联实体
        related_entities = []
        for rel in relations:
            if rel['subject'] == entity_text:
                related_entities.append({
                    'entity': rel['object'],
                    'type': rel['object_type'],
                    'relation': rel['predicate'],
                    'direction': 'outgoing'
                })
            else:
                related_entities.append({
                    'entity': rel['subject'],
                    'type': rel['subject_type'],
                    'relation': rel['predicate'],
                    'direction': 'incoming'
                })

        return {
            'found': True,
            'entity': entity,
            'relations': relations,
            'related_entities': related_entities
        }

    def query_relation(self, subject: str = None, predicate: str = None, obj: str = None) -> List[Dict]:
        """查询关系"""
        all_relations = self.storage.get_all_relations()
        results = []

        for rel in all_relations:
            match = True
            if subject and rel['subject'] != subject:
                match = False
            if predicate and rel['predicate'] != predicate:
                match = False
            if obj and rel['object'] != obj:
                match = False
            if match:
                results.append(rel)

        return results

    def query_path(self, start_entity: str, end_entity: str, max_depth: int = 3) -> List[List[Dict]]:
        """查询两个实体之间的路径"""
        paths = []
        visited = set()
        self._dfs_paths(start_entity, end_entity, max_depth, [], visited, paths)
        return paths

    def _dfs_paths(self, current: str, target: str, depth: int,
                   current_path: List[Dict], visited: set, all_paths: List[List[Dict]]):
        """深度优先搜索路径"""
        if depth <= 0:
            return

        if current == target and current_path:
            all_paths.append(current_path.copy())
            return

        visited.add(current)
        relations = self.storage.get_entity_relations(current)

        for rel in relations:
            next_entity = rel['object'] if rel['subject'] == current else rel['subject']

            if next_entity not in visited:
                step = {
                    'from': current,
                    'to': next_entity,
                    'relation': rel['predicate']
                }
                current_path.append(step)
                self._dfs_paths(next_entity, target, depth - 1, current_path, visited, all_paths)
                current_path.pop()

        visited.remove(current)

    def query_subgraph(self, center_entity: str, depth: int = 2) -> Dict:
        """查询以某实体为中心的子图"""
        nodes = []
        links = []
        visited = set()

        self._collect_subgraph(center_entity, depth, visited, nodes, links)

        return {'nodes': nodes, 'links': links}

    def _collect_subgraph(self, entity: str, depth: int, visited: set,
                          nodes: List[Dict], links: List[Dict]):
        """收集子图数据"""
        if depth <= 0 or entity in visited:
            return

        visited.add(entity)
        entity_data = self.storage.get_entity(entity)

        if entity_data:
            nodes.append({
                'id': entity_data['id'],
                'label': entity,
                'type': entity_data['type'],
                'count': entity_data.get('count', 1)
            })

        relations = self.storage.get_entity_relations(entity)

        for rel in relations:
            source_entity = self.storage.get_entity(rel['subject'])
            target_entity = self.storage.get_entity(rel['object'])

            if source_entity and target_entity:
                links.append({
                    'source': source_entity['id'],
                    'target': target_entity['id'],
                    'label': rel['predicate']
                })

                next_entity = rel['object'] if rel['subject'] == entity else rel['subject']
                self._collect_subgraph(next_entity, depth - 1, visited, nodes, links)

    def query_by_type(self, entity_type: str) -> List[Dict]:
        """按类型查询实体"""
        entities = self.storage.get_all_entities()
        return [e for e in entities if e['type'] == entity_type]

    def query_keyword(self, keyword: str) -> Dict:
        """关键词查询"""
        entities = self.storage.search_entities(keyword)
        entity_texts = [e['text'] for e in entities]

        relations = []
        for rel in self.storage.get_all_relations():
            if rel['subject'] in entity_texts or rel['object'] in entity_texts:
                relations.append(rel)

        return {
            'entities': entities,
            'relations': relations
        }
