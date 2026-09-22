"""
NLP处理管道 - 整合分词、NER、关系抽取
"""
from typing import List, Dict
from backend.nlp.tokenizer import ChineseTokenizer
from backend.nlp.ner import NamedEntityRecognizer
from backend.nlp.relation_extractor import RelationExtractor


class NLPPipeline:
    """NLP处理管道"""

    def __init__(self):
        self.tokenizer = ChineseTokenizer()
        self.ner = NamedEntityRecognizer()
        self.relation_extractor = RelationExtractor()

    def process(self, text: str) -> Dict:
        """完整处理文本，返回实体和关系"""
        # 1. 分句
        sentences = self.tokenizer.segment_sentences(text)

        all_entities = []
        all_relations = []
        processed_sentences = []

        for sentence in sentences:
            if len(sentence) < 5:  # 过短句子跳过
                continue

            # 2. 命名实体识别
            entities = self.ner.recognize_with_context(sentence)

            # 3. 关系抽取
            relations = self.relation_extractor.extract_relations(sentence, entities)

            all_entities.extend(entities)
            all_relations.extend(relations)

            processed_sentences.append({
                'text': sentence,
                'entities': entities,
                'relations': relations
            })

        # 4. 实体去重
        unique_entities = self._deduplicate_entities(all_entities)

        # 5. 关系去重
        unique_relations = self._deduplicate_relations(all_relations)

        return {
            'text': text,
            'sentences': processed_sentences,
            'entities': unique_entities,
            'relations': unique_relations,
            'triples': [(r['subject'], r['predicate'], r['object']) for r in unique_relations]
        }

    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """实体去重"""
        seen = {}
        for entity in entities:
            key = (entity['text'], entity['type'])
            if key not in seen:
                seen[key] = entity
        return list(seen.values())

    def _deduplicate_relations(self, relations: List[Dict]) -> List[Dict]:
        """关系去重"""
        seen = {}
        for relation in relations:
            key = (relation['subject'], relation['predicate'], relation['object'])
            if key not in seen:
                seen[key] = relation
        return list(seen.values())

    def extract_keywords(self, text: str, topk: int = 10) -> List[str]:
        """提取关键词"""
        import jieba.analyse
        return jieba.analyse.extract_tags(text, topK=topk)
