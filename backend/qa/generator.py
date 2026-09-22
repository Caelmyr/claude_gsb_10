"""
答案生成模块 - 基于图谱检索的答案生成
"""
from typing import List, Dict
from backend.qa.retriever import SemanticRetriever
from backend.qa.dialogue import DialogueManager
from backend.graph.storage import GraphStorage


class AnswerGenerator:
    """答案生成器"""

    def __init__(self, storage: GraphStorage):
        self.storage = storage
        self.retriever = SemanticRetriever(storage)
        self.dialogue_manager = DialogueManager()

    def generate_answer(self, question: str, session_id: str = None) -> Dict:
        """生成问题答案"""
        # 如果没有会话，创建新会话
        if not session_id:
            session_id = self.dialogue_manager.create_session()

        # 添加用户消息
        self.dialogue_manager.add_message(session_id, 'user', question)

        # 获取对话上下文
        context = self.dialogue_manager.get_recent_context(session_id)

        # 检索相关信息
        retrieved = self.retriever.retrieve(question)

        # 构建答案
        answer = self._build_answer(question, retrieved, context)

        # 添加助手回复
        self.dialogue_manager.add_message(session_id, 'assistant', answer['text'], {
            'sources': answer.get('sources', []),
            'confidence': answer.get('confidence', 0)
        })

        return {
            'session_id': session_id,
            'answer': answer['text'],
            'sources': answer.get('sources', []),
            'confidence': answer.get('confidence', 0),
            'related_entities': answer.get('related_entities', [])
        }

    def _build_answer(self, question: str, retrieved: List[Dict], context: str) -> Dict:
        """构建答案"""
        if not retrieved:
            return {
                'text': '抱歉，我没有找到相关信息来回答您的问题。请尝试换个方式提问，或者先上传相关文档。',
                'confidence': 0.1,
                'sources': []
            }

        # 分析问题类型
        question_type = self._analyze_question_type(question)

        # 根据问题类型构建答案
        if question_type == 'entity_info':
            return self._answer_entity_info(question, retrieved)
        elif question_type == 'relation':
            return self._answer_relation(question, retrieved)
        elif question_type == 'list':
            return self._answer_list(question, retrieved)
        else:
            return self._answer_general(question, retrieved, context)

    def _analyze_question_type(self, question: str) -> str:
        """分析问题类型"""
        if any(kw in question for kw in ['是什么', '是谁', '什么是', '谁是']):
            return 'entity_info'
        elif any(kw in question for kw in ['关系', '关联', '联系', '属于', '位于']):
            return 'relation'
        elif any(kw in question for kw in ['哪些', '列举', '有什么', '包括']):
            return 'list'
        else:
            return 'general'

    def _answer_entity_info(self, question: str, retrieved: List[Dict]) -> Dict:
        """回答实体信息类问题"""
        entities = [r['data'] for r in retrieved if r['type'] == 'entity']

        if not entities:
            return {
                'text': '未找到相关实体信息。',
                'confidence': 0.3,
                'sources': []
            }

        entity = entities[0]
        relations = self.storage.get_entity_relations(entity['text'])

        answer_parts = [f"**{entity['text']}** 是一个 {entity['type']} 类型的实体。"]

        if relations:
            answer_parts.append("\n相关信息：")
            for rel in relations[:5]:
                if rel['subject'] == entity['text']:
                    answer_parts.append(f"- {rel['predicate']} {rel['object']}")
                else:
                    answer_parts.append(f"- 被 {rel['subject']} {rel['predicate']}")

        return {
            'text': '\n'.join(answer_parts),
            'confidence': 0.7,
            'sources': [entity['text']],
            'related_entities': [{'text': e['text'], 'type': e['type']} for e in entities[:5]]
        }

    def _answer_relation(self, question: str, retrieved: List[Dict]) -> Dict:
        """回答关系类问题"""
        relations = [r['data'] for r in retrieved if r['type'] == 'relation']

        if not relations:
            return {
                'text': '未找到明确的关系信息。',
                'confidence': 0.3,
                'sources': []
            }

        answer_parts = ["根据知识图谱，找到以下关系："]
        for rel in relations[:5]:
            answer_parts.append(f"- {rel['subject']} {rel['predicate']} {rel['object']}")

        return {
            'text': '\n'.join(answer_parts),
            'confidence': 0.7,
            'sources': [rel['subject'] for rel in relations[:3]]
        }

    def _answer_list(self, question: str, retrieved: List[Dict]) -> Dict:
        """回答列举类问题"""
        entities = [r['data'] for r in retrieved if r['type'] == 'entity']

        if not entities:
            return {
                'text': '未找到相关实体。',
                'confidence': 0.3,
                'sources': []
            }

        answer_parts = ["找到以下相关实体："]
        for entity in entities[:10]:
            answer_parts.append(f"- {entity['text']} ({entity['type']})")

        return {
            'text': '\n'.join(answer_parts),
            'confidence': 0.7,
            'sources': [entity['text'] for entity in entities[:5]]
        }

    def _answer_general(self, question: str, retrieved: List[Dict], context: str) -> Dict:
        """回答一般问题"""
        entities = [r['data'] for r in retrieved if r['type'] == 'entity']
        relations = [r['data'] for r in retrieved if r['type'] == 'relation']

        answer_parts = ["根据知识图谱中的信息："]

        if entities:
            answer_parts.append("\n相关实体：")
            for entity in entities[:5]:
                answer_parts.append(f"- {entity['text']} ({entity['type']})")

        if relations:
            answer_parts.append("\n相关关系：")
            for rel in relations[:5]:
                answer_parts.append(f"- {rel['subject']} {rel['predicate']} {rel['object']}")

        if not entities and not relations:
            return {
                'text': '抱歉，暂时无法找到相关信息。请尝试上传更多文档或换个方式提问。',
                'confidence': 0.2,
                'sources': []
            }

        return {
            'text': '\n'.join(answer_parts),
            'confidence': 0.6,
            'sources': [entity['text'] for entity in entities[:3]]
        }
