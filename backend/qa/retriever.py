"""
语义检索模块 - 基于图谱的语义检索
"""
from typing import List, Dict
from backend.graph.storage import GraphStorage
from backend.nlp.tokenizer import ChineseTokenizer


class SemanticRetriever:
    """语义检索器"""

    def __init__(self, storage: GraphStorage):
        self.storage = storage
        self.tokenizer = ChineseTokenizer()

    def retrieve(self, query: str, topk: int = 5) -> List[Dict]:
        """检索与查询相关的实体和关系"""
        # 分词
        keywords = self.tokenizer.tokenize(query)

        # 提取关键词（过滤停用词）
        keywords = [kw for kw in keywords if len(kw) > 1]

        # 搜索相关实体
        relevant_entities = []
        for keyword in keywords:
            entities = self.storage.search_entities(keyword)
            relevant_entities.extend(entities)

        # 去重
        seen = set()
        unique_entities = []
        for entity in relevant_entities:
            if entity['text'] not in seen:
                seen.add(entity['text'])
                unique_entities.append(entity)

        # 获取相关关系
        relevant_relations = []
        for entity in unique_entities[:topk]:
            relations = self.storage.get_entity_relations(entity['text'])
            relevant_relations.extend(relations)

        # 计算相关性分数
        scored_results = self._score_results(query, unique_entities, relevant_relations)

        return scored_results[:topk]

    def _score_results(self, query: str, entities: List[Dict], relations: List[Dict]) -> List[Dict]:
        """计算结果相关性分数"""
        query_keywords = set(self.tokenizer.tokenize(query))

        scored = []
        for entity in entities:
            entity_keywords = set(self.tokenizer.tokenize(entity['text']))
            overlap = len(query_keywords & entity_keywords)
            score = overlap / max(len(query_keywords), 1)
            scored.append({
                'type': 'entity',
                'data': entity,
                'score': score
            })

        for relation in relations:
            rel_text = f"{relation['subject']} {relation['predicate']} {relation['object']}"
            rel_keywords = set(self.tokenizer.tokenize(rel_text))
            overlap = len(query_keywords & rel_keywords)
            score = overlap / max(len(query_keywords), 1)
            scored.append({
                'type': 'relation',
                'data': relation,
                'score': score
            })

        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored

    def retrieve_context(self, query: str, max_entities: int = 10) -> str:
        """检索并构建上下文文本"""
        results = self.retrieve(query, topk=max_entities)

        context_parts = []
        for result in results:
            if result['type'] == 'entity':
                entity = result['data']
                context_parts.append(f"实体: {entity['text']} (类型: {entity['type']})")
            elif result['type'] == 'relation':
                rel = result['data']
                context_parts.append(f"关系: {rel['subject']} -[{rel['predicate']}]-> {rel['object']}")

        return '\n'.join(context_parts)
