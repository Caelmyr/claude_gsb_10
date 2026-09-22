"""
知识图谱问答系统 - 配置模块
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# 数据存储路径
DOCUMENTS_DIR = os.path.join(DATA_DIR, 'documents')
TRIPLES_DIR = os.path.join(DATA_DIR, 'triples')
GRAPH_DIR = os.path.join(DATA_DIR, 'graph')
SESSIONS_DIR = os.path.join(DATA_DIR, 'sessions')

# NLP配置
ENTITY_TYPES = ['PERSON', 'ORG', 'LOCATION', 'TIME', 'CONCEPT', 'EVENT', 'OTHER']
RELATION_TYPES = ['属于', '位于', '参与', '包含', '相关', '导致', '使用', '创建', '属于']

# 图谱分片配置
GRAPH_SHARDS = {
    'PERSON': 'person.json',
    'ORG': 'org.json',
    'LOCATION': 'location.json',
    'TIME': 'time.json',
    'CONCEPT': 'concept.json',
    'EVENT': 'event.json',
    'OTHER': 'other.json'
}

# API配置
API_HOST = '0.0.0.0'
API_PORT = 5000
