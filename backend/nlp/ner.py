"""
命名实体识别模块 - 基于规则和词典的NER
"""
import re
from typing import List, Dict, Tuple
from backend.utils.config import ENTITY_TYPES


class NamedEntityRecognizer:
    """命名实体识别器"""

    def __init__(self):
        self.entity_patterns = self._build_patterns()
        self.entity_cache = {}

    def _build_patterns(self) -> Dict[str, List]:
        """构建实体识别模式"""
        return {
            'PERSON': [
                r'[一-龥]{2,4}(?:先生|女士|教授|博士|老师|总|经理|院长|主任)',
                r'(?:我|你|他|她|它|我们|你们|他们)(?:的)?(?:朋友|同事|同学|老师|领导)',
            ],
            'ORG': [
                r'[一-龥]{2,10}(?:公司|集团|大学|学院|研究所|研究院|机构|组织|协会|基金会)',
                r'(?:中国|美国|日本|英国|法国|德国|俄罗斯)[一-龥]{2,8}(?:部|局|委|署)',
            ],
            'LOCATION': [
                r'[一-龥]{2,8}(?:省|市|区|县|镇|村|街|路|道|巷)',
                r'(?:中国|美国|日本|英国|法国|德国|俄罗斯|印度|巴西|澳大利亚)',
                r'(?:北京|上海|广州|深圳|杭州|南京|成都|重庆|武汉|西安)',
            ],
            'TIME': [
                r'\d{4}年(?:\d{1,2}月)?(?:\d{1,2}日)?',
                r'(?:今天|昨天|明天|前天|后天|本周|上周|下周|本月|上月|下月)',
                r'(?:早上|上午|中午|下午|傍晚|晚上|凌晨)',
            ],
            'CONCEPT': [
                r'[一-龥]{2,6}(?:理论|方法|技术|系统|模型|算法|框架|模式)',
            ],
            'EVENT': [
                r'[一-龥]{2,8}(?:会议|比赛|活动|运动|革命|战争|改革)',
            ]
        }

    def recognize(self, text: str) -> List[Dict]:
        """识别文本中的实体"""
        entities = []
        seen = set()

        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    entity_text = match.group()
                    if entity_text not in seen:
                        seen.add(entity_text)
                        entities.append({
                            'text': entity_text,
                            'type': entity_type,
                            'start': match.start(),
                            'end': match.end()
                        })

        # 按位置排序
        entities.sort(key=lambda x: x['start'])
        return entities

    def recognize_with_context(self, text: str, context_window: int = 50) -> List[Dict]:
        """带上下文的实体识别"""
        entities = self.recognize(text)

        for entity in entities:
            start = max(0, entity['start'] - context_window)
            end = min(len(text), entity['end'] + context_window)
            entity['context'] = text[start:end]

        return entities
