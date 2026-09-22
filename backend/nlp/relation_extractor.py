"""
关系抽取模块 - 基于模式匹配和依存句法的关系抽取
"""
import re
from typing import List, Dict, Tuple


class RelationExtractor:
    """关系抽取器"""

    def __init__(self):
        self.relation_patterns = self._build_relation_patterns()

    def _build_relation_patterns(self) -> Dict[str, List[str]]:
        """构建关系抽取模式"""
        return {
            '属于': [
                r'(.+?)(?:是|属于|隶属于)(.+?)(?:[，。,.]|$)',
                r'(.+?)(?:的)(.+?)(?:是|为|属于)',
            ],
            '位于': [
                r'(.+?)(?:位于|坐落在|在|处于)(.+?)(?:[，。,.]|$)',
                r'(.+?)(?:的)(?:位置|地址|地点)(?:是|在|位于)(.+?)(?:[，。,.]|$)',
            ],
            '包含': [
                r'(.+?)(?:包含|包括|含有|具有|拥有)(.+?)(?:[，。,.]|$)',
                r'(.+?)(?:的)(?:内容|成员|部分)(?:是|包括|包含)(.+?)(?:[，。,.]|$)',
            ],
            '参与': [
                r'(.+?)(?:参加|参与|加入|出席)(.+?)(?:[，。,.]|$)',
                r'(.+?)(?:在|到)(.+?)(?:参加|参与|出席)',
            ],
            '创建': [
                r'(.+?)(?:创建|创立|建立|创办|开发)(?:了)?(.+?)(?:[，。,.]|$)',
                r'(.+?)(?:被|由)(.+?)(?:创建|创立|建立|创办)',
            ],
            '使用': [
                r'(.+?)(?:使用|采用|运用|利用)(?:了)?(.+?)(?:[，。,.]|$)',
                r'(.+?)(?:用|利用)(.+?)(?:来|去|进行)',
            ],
            '导致': [
                r'(.+?)(?:导致|引起|造成|产生)(?:了)?(.+?)(?:[，。,.]|$)',
                r'(.+?)(?:因为|由于)(.+?)(?:所以|因此|从而)',
            ],
            '相关': [
                r'(.+?)(?:与|和|跟|同)(.+?)(?:有关|相关|联系|关联)',
                r'(.+?)(?:关联|联系|关系)(?:了)?(.+?)(?:[，。,.]|$)',
            ],
        }

    def extract_relations(self, text: str, entities: List[Dict]) -> List[Dict]:
        """从文本中抽取实体关系"""
        relations = []
        seen = set()

        for relation_type, patterns in self.relation_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    groups = match.groups()
                    if len(groups) >= 2:
                        subject = groups[0].strip()
                        obj = groups[1].strip()

                        # 检查是否与已识别实体匹配
                        subject_entity = self._find_matching_entity(subject, entities)
                        object_entity = self._find_matching_entity(obj, entities)

                        if subject_entity and object_entity:
                            relation_key = (subject_entity['text'], relation_type, object_entity['text'])
                            if relation_key not in seen:
                                seen.add(relation_key)
                                relations.append({
                                    'subject': subject_entity['text'],
                                    'subject_type': subject_entity['type'],
                                    'predicate': relation_type,
                                    'object': object_entity['text'],
                                    'object_type': object_entity['type'],
                                    'confidence': 0.8,
                                    'source_text': match.group()
                                })

        return relations

    def _find_matching_entity(self, text: str, entities: List[Dict]) -> Dict:
        """查找与文本匹配的实体"""
        text = text.strip()
        for entity in entities:
            if entity['text'] in text or text in entity['text']:
                return entity
        return None

    def extract_triples(self, text: str, entities: List[Dict]) -> List[Tuple]:
        """抽取三元组 (主语, 谓语, 宾语)"""
        relations = self.extract_relations(text, entities)
        return [(r['subject'], r['predicate'], r['object']) for r in relations]
