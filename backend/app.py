"""
知识图谱问答系统 - Flask后端API
"""
import os
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from backend.utils.config import API_HOST, API_PORT, DOCUMENTS_DIR, TRIPLES_DIR
from backend.utils.text_extractor import extract_text
from backend.nlp.pipeline import NLPPipeline
from backend.graph.builder import GraphBuilder
from backend.graph.storage import GraphStorage
from backend.graph.query import GraphQuery
from backend.qa.generator import AnswerGenerator
from backend.qa.dialogue import DialogueManager

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# 初始化组件
nlp_pipeline = NLPPipeline()
graph_storage = GraphStorage()
graph_builder = GraphBuilder(graph_storage)
graph_query = GraphQuery(graph_storage)
answer_generator = AnswerGenerator(graph_storage)
dialogue_manager = DialogueManager()


# ==================== 前端页面路由 ====================

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


# ==================== 文档管理API ====================

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    """上传文档"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400

    # 检查文件类型
    allowed_extensions = {'.txt', '.pdf'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({'error': f'不支持的文件格式: {ext}'}), 400

    # 保存文件
    doc_id = str(uuid.uuid4())[:8]
    filename = f"{doc_id}{ext}"
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    file.save(filepath)

    # 提取文本
    try:
        text = extract_text(filepath)
    except Exception as e:
        return jsonify({'error': f'文本提取失败: {str(e)}'}), 500

    # 保存文档信息
    doc_info = {
        'id': doc_id,
        'filename': file.filename,
        'stored_filename': filename,
        'upload_time': datetime.now().isoformat(),
        'text_length': len(text),
        'text_preview': text[:500]
    }

    doc_info_path = os.path.join(DOCUMENTS_DIR, f'{doc_id}.json')
    with open(doc_info_path, 'w', encoding='utf-8') as f:
        json.dump(doc_info, f, ensure_ascii=False, indent=2)

    return jsonify({
        'success': True,
        'document': doc_info,
        'text_preview': text[:1000]
    })


@app.route('/api/documents', methods=['GET'])
def list_documents():
    """获取文档列表"""
    documents = []
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)

    for filename in os.listdir(DOCUMENTS_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(DOCUMENTS_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                doc = json.load(f)
                documents.append(doc)

    documents.sort(key=lambda x: x.get('upload_time', ''), reverse=True)
    return jsonify({'documents': documents})


@app.route('/api/documents/<doc_id>', methods=['GET'])
def get_document(doc_id):
    """获取文档详情"""
    doc_info_path = os.path.join(DOCUMENTS_DIR, f'{doc_id}.json')
    if not os.path.exists(doc_info_path):
        return jsonify({'error': '文档不存在'}), 404

    with open(doc_info_path, 'r', encoding='utf-8') as f:
        doc = json.load(f)

    # 读取完整文本
    filepath = os.path.join(DOCUMENTS_DIR, doc['stored_filename'])
    if os.path.exists(filepath):
        doc['full_text'] = extract_text(filepath)

    return jsonify(doc)


@app.route('/api/documents/<doc_id>/parse', methods=['POST'])
def parse_document(doc_id):
    """解析文档并提取实体关系"""
    doc_info_path = os.path.join(DOCUMENTS_DIR, f'{doc_id}.json')
    if not os.path.exists(doc_info_path):
        return jsonify({'error': '文档不存在'}), 404

    with open(doc_info_path, 'r', encoding='utf-8') as f:
        doc = json.load(f)

    filepath = os.path.join(DOCUMENTS_DIR, doc['stored_filename'])
    if not os.path.exists(filepath):
        return jsonify({'error': '文档文件不存在'}), 404

    # 同一文档重复解析时，先清理上一次解析写入的图谱数据，避免重复累加
    graph_storage.remove_document_data(doc_id)

    # 构建图谱
    result = graph_builder.build_from_document(filepath, doc_id)

    # 保存三元组
    triples_path = os.path.join(TRIPLES_DIR, f'{doc_id}.json')
    os.makedirs(TRIPLES_DIR, exist_ok=True)
    with open(triples_path, 'w', encoding='utf-8') as f:
        json.dump({
            'doc_id': doc_id,
            'triples': result['triples'],
            'entities': result['entities'],
            'relations': result['relations'],
            'parse_time': datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

    return jsonify({
        'success': True,
        'doc_id': doc_id,
        'entities_count': result['entities_count'],
        'relations_count': result['relations_count'],
        'triples': result['triples'][:50],  # 返回前50个三元组
        'entities': result['entities'][:50]
    })


@app.route('/api/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """删除文档，并级联清理其生成的三元组和图谱数据"""
    doc_info_path = os.path.join(DOCUMENTS_DIR, f'{doc_id}.json')
    if not os.path.exists(doc_info_path):
        return jsonify({'error': '文档不存在'}), 404

    with open(doc_info_path, 'r', encoding='utf-8') as f:
        doc = json.load(f)

    # 删除原始文档文件
    stored_path = os.path.join(DOCUMENTS_DIR, doc.get('stored_filename', ''))
    if os.path.exists(stored_path):
        os.remove(stored_path)

    # 删除解析生成的三元组文件
    triples_path = os.path.join(TRIPLES_DIR, f'{doc_id}.json')
    if os.path.exists(triples_path):
        os.remove(triples_path)

    # 级联清理图谱中由该文档生成的实体和关系
    cleanup = graph_storage.remove_document_data(doc_id)

    # 删除文档元信息
    os.remove(doc_info_path)

    return jsonify({
        'success': True,
        'doc_id': doc_id,
        **cleanup
    })


# ==================== 实体关系API ====================

@app.route('/api/entities', methods=['GET'])
def list_entities():
    """获取所有实体"""
    entities = graph_storage.get_all_entities()
    return jsonify({'entities': entities})


@app.route('/api/entities/<entity_text>', methods=['GET'])
def get_entity(entity_text):
    """获取实体详情"""
    result = graph_query.query_entity(entity_text)
    return jsonify(result)


@app.route('/api/relations', methods=['GET'])
def list_relations():
    """获取所有关系"""
    relations = graph_storage.get_all_relations()
    return jsonify({'relations': relations})


@app.route('/api/triples', methods=['POST'])
def add_triple():
    """手动添加三元组"""
    data = request.json
    required_fields = ['subject', 'subject_type', 'predicate', 'object', 'object_type']

    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'缺少字段: {field}'}), 400

    result = graph_builder.add_triple(
        data['subject'], data['subject_type'],
        data['predicate'],
        data['object'], data['object_type']
    )

    return jsonify(result)


@app.route('/api/triples/batch', methods=['POST'])
def add_triples_batch():
    """批量添加三元组"""
    data = request.json
    triples = data.get('triples', [])

    results = []
    for triple in triples:
        try:
            result = graph_builder.add_triple(
                triple['subject'], triple['subject_type'],
                triple['predicate'],
                triple['object'], triple['object_type']
            )
            results.append(result)
        except Exception as e:
            results.append({'error': str(e)})

    return jsonify({'results': results})


# ==================== 图谱查询API ====================

@app.route('/api/graph/data', methods=['GET'])
def get_graph_data():
    """获取图谱可视化数据"""
    data = graph_builder.get_graph_data()
    return jsonify(data)


@app.route('/api/graph/query', methods=['POST'])
def query_graph():
    """查询图谱"""
    data = request.json
    query_text = data.get('query', '')

    if not query_text:
        return jsonify({'error': '查询内容为空'}), 400

    result = graph_query.query_keyword(query_text)
    return jsonify(result)


@app.route('/api/graph/subgraph/<entity_text>', methods=['GET'])
def get_subgraph(entity_text):
    """获取实体子图"""
    depth = request.args.get('depth', 2, type=int)
    result = graph_query.query_subgraph(entity_text, depth)
    return jsonify(result)


@app.route('/api/graph/path', methods=['POST'])
def find_path():
    """查找两个实体之间的路径"""
    data = request.json
    start = data.get('start')
    end = data.get('end')
    max_depth = data.get('max_depth', 3)

    if not start or not end:
        return jsonify({'error': '需要提供起始和结束实体'}), 400

    paths = graph_query.query_path(start, end, max_depth)
    return jsonify({'paths': paths})


@app.route('/api/graph/statistics', methods=['GET'])
def get_statistics():
    """获取图谱统计信息"""
    stats = graph_builder.get_statistics()
    return jsonify(stats)


# ==================== 问答API ====================

@app.route('/api/qa/ask', methods=['POST'])
def ask_question():
    """提问"""
    data = request.json
    question = data.get('question', '')
    session_id = data.get('session_id')

    if not question:
        return jsonify({'error': '问题为空'}), 400

    result = answer_generator.generate_answer(question, session_id)
    return jsonify(result)


@app.route('/api/qa/sessions', methods=['GET'])
def list_sessions():
    """获取会话列表"""
    sessions = dialogue_manager.get_all_sessions()
    return jsonify({'sessions': sessions})


@app.route('/api/qa/sessions', methods=['POST'])
def create_session():
    """创建新会话"""
    data = request.json or {}
    title = data.get('title')
    session_id = dialogue_manager.create_session(title)
    return jsonify({'session_id': session_id})


@app.route('/api/qa/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """获取会话详情"""
    session = dialogue_manager.get_session(session_id)
    if not session:
        return jsonify({'error': '会话不存在'}), 404
    return jsonify(session)


@app.route('/api/qa/sessions/<session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    """获取会话消息"""
    messages = dialogue_manager.get_session_messages(session_id)
    return jsonify({'messages': messages})


@app.route('/api/qa/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """删除会话"""
    success = dialogue_manager.delete_session(session_id)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': '会话不存在'}), 404


# ==================== 标注API ====================

@app.route('/api/annotate/entity', methods=['POST'])
def annotate_entity():
    """标注实体"""
    data = request.json
    entity_text = data.get('text')
    entity_type = data.get('type')
    doc_id = data.get('doc_id')

    if not entity_text or not entity_type:
        return jsonify({'error': '缺少实体文本或类型'}), 400

    graph_storage.add_entity(entity_text, entity_type, {'doc_id': doc_id, 'manual': True})
    return jsonify({'success': True, 'entity': entity_text, 'type': entity_type})


@app.route('/api/annotate/relation', methods=['POST'])
def annotate_relation():
    """标注关系"""
    data = request.json
    required_fields = ['subject', 'subject_type', 'predicate', 'object', 'object_type']

    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'缺少字段: {field}'}), 400

    graph_storage.add_relation(
        data['subject'], data['subject_type'],
        data['predicate'],
        data['object'], data['object_type'],
        {'manual': True}
    )

    return jsonify({'success': True})


if __name__ == '__main__':
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    os.makedirs(TRIPLES_DIR, exist_ok=True)
    print(f"知识图谱问答系统启动中...")
    print(f"访问地址: http://localhost:{API_PORT}")
    app.run(host=API_HOST, port=API_PORT, debug=True)
