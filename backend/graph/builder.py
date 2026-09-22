"""
图谱构建模块 - 从文档构建知识图谱
"""
from typing import List, Dict
from backend.nlp.pipeline import NLPPipeline
from backend.graph.storage import GraphStorage


class GraphBuilder:
    """图谱构建器"""

    def __init__(self):
        self.nlp_pipeline = NLPPipeline()
        self.storage = GraphStorage()

    def build_from_text(self, text: str, doc_id: str = None) -> Dict:
        """从文本构建图谱"""
        # NLP处理
        result = self.nlp_pipeline.process(text)

        # 添加实体到图谱
        for entity in result['entities']:
            self.storage.add_entity(
                entity['text'],
                entity['type'],
                {'context': entity.get('context', ''), 'doc_id': doc_id}
            )

        # 添加关系到图谱
        for relation in result['relations']:
            self.storage.add_relation(
                relation['subject'],
                relation['subject_type'],
                relation['predicate'],
                relation['object'],
                relation['object_type'],
                {'source_text': relation.get('source_text', ''), 'doc_id': doc_id}
            )

        return {
            'doc_id': doc_id,
            'entities_count': len(result['entities']),
            'relations_count': len(result['relations']),
            'triples': result['triples'],
            'entities': result['entities'],
            'relations': result['relations']
        }

    def build_from_document(self, doc_path: str, doc_id: str) -> Dict:
        """从文档文件构建图谱"""
        from backend.utils.text_extractor import extract_text
        text = extract_text(doc_path)
        return self.build_from_text(text, doc_id)

    def add_triple(self, subject: str, subject_type: str, predicate: str,
                   obj: str, object_type: str) -> Dict:
        """手动添加三元组"""
        self.storage.add_relation(subject, subject_type, predicate, obj, object_type)
        return {'status': 'success', 'triple': (subject, predicate, obj)}

    def get_graph_data(self) -> Dict:
        """获取图谱可视化数据"""
        return self.storage.get_graph_data()

    def get_statistics(self) -> Dict:
        """获取图谱统计"""
        return self.storage.get_statistics()

    def query(self, query_text: str) -> Dict:
        """查询图谱"""
        from backend.graph.query import GraphQuery
        query_engine = GraphQuery(self.storage)
        return query_engine.query_keyword(query_text)
