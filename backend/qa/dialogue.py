"""
多轮对话管理模块 - 上下文管理和会话持久化
"""
import json
import os
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from backend.utils.config import SESSIONS_DIR


class DialogueManager:
    """多轮对话管理器"""

    def __init__(self):
        self.sessions = {}
        self._ensure_directory()
        self._load_sessions()

    def _ensure_directory(self):
        """确保目录存在"""
        os.makedirs(SESSIONS_DIR, exist_ok=True)

    def _load_sessions(self):
        """加载所有会话"""
        for filename in os.listdir(SESSIONS_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(SESSIONS_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    session = json.load(f)
                    self.sessions[session['id']] = session

    def _save_session(self, session_id: str):
        """保存会话到文件"""
        if session_id in self.sessions:
            filepath = os.path.join(SESSIONS_DIR, f'{session_id}.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.sessions[session_id], f, ensure_ascii=False, indent=2)

    def create_session(self, title: str = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())[:8]
        self.sessions[session_id] = {
            'id': session_id,
            'title': title or f'会话 {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'messages': [],
            'context': {
                'entities': [],
                'relations': [],
                'topic': None
            }
        }
        self._save_session(session_id)
        return session_id

    def add_message(self, session_id: str, role: str, content: str, metadata: Dict = None) -> Dict:
        """添加消息到会话"""
        if session_id not in self.sessions:
            raise ValueError(f"会话不存在: {session_id}")

        message = {
            'id': str(uuid.uuid4())[:8],
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }

        self.sessions[session_id]['messages'].append(message)
        self.sessions[session_id]['updated_at'] = datetime.now().isoformat()

        # 更新上下文
        self._update_context(session_id, content)

        self._save_session(session_id)
        return message

    def _update_context(self, session_id: str, content: str):
        """更新会话上下文"""
        from backend.nlp.ner import NamedEntityRecognizer

        ner = NamedEntityRecognizer()
        entities = ner.recognize(content)

        context = self.sessions[session_id]['context']

        # 添加新实体到上下文
        for entity in entities:
            if entity['text'] not in [e['text'] for e in context['entities']]:
                context['entities'].append({
                    'text': entity['text'],
                    'type': entity['type']
                })

        # 保持上下文大小合理
        if len(context['entities']) > 20:
            context['entities'] = context['entities'][-20:]

    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        return self.sessions.get(session_id)

    def get_session_messages(self, session_id: str) -> List[Dict]:
        """获取会话消息"""
        session = self.sessions.get(session_id)
        if session:
            return session['messages']
        return []

    def get_recent_context(self, session_id: str, n_messages: int = 5) -> str:
        """获取最近n条消息的上下文"""
        messages = self.get_session_messages(session_id)
        recent = messages[-n_messages:] if len(messages) > n_messages else messages

        context_parts = []
        for msg in recent:
            role = "用户" if msg['role'] == 'user' else "助手"
            context_parts.append(f"{role}: {msg['content']}")

        return '\n'.join(context_parts)

    def get_all_sessions(self) -> List[Dict]:
        """获取所有会话摘要"""
        sessions = []
        for session_id, session in self.sessions.items():
            sessions.append({
                'id': session['id'],
                'title': session['title'],
                'created_at': session['created_at'],
                'updated_at': session['updated_at'],
                'message_count': len(session['messages'])
            })

        sessions.sort(key=lambda x: x['updated_at'], reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            filepath = os.path.join(SESSIONS_DIR, f'{session_id}.json')
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        return False
