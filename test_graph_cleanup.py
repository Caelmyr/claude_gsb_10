"""验证文档删除时图谱数据的级联清理逻辑（不依赖flask/jieba）"""
import os
import sys
import json
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 使用临时数据目录，避免污染真实数据
tmp_data = tempfile.mkdtemp(prefix='kg_test_')

import backend.utils.config as config
config.DATA_DIR = tmp_data
config.DOCUMENTS_DIR = os.path.join(tmp_data, 'documents')
config.TRIPLES_DIR = os.path.join(tmp_data, 'triples')
config.GRAPH_DIR = os.path.join(tmp_data, 'graph')

from backend.graph.storage import GraphStorage

passed = []
failed = []


def check(name, cond, detail=''):
    (passed if cond else failed).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


storage = GraphStorage()

# 模拟文档A解析：实体 清华(ORG)、北京(LOCATION)，关系 清华-位于->北京
storage.add_entity('清华大学', 'ORG', doc_id='A')
storage.add_entity('北京', 'LOCATION', doc_id='A')
storage.add_relation('清华大学', 'ORG', '位于', '北京', 'LOCATION', doc_id='A')

# 同一实体内被关系重复add不应翻倍（模拟builder旧逻辑：先add_entity再add_relation）
# 验证计数
qh = storage.get_entity('清华大学')
check('单次解析实体count=1（修复翻倍）', qh['count'] == 1, f"count={qh['count']}")
check('实体doc_ids记录来源A', qh['doc_ids'] == ['A'])

# 重复解析文档A：再次写入同样数据
storage.add_entity('清华大学', 'ORG', doc_id='A')
storage.add_entity('北京', 'LOCATION', doc_id='A')
storage.add_relation('清华大学', 'ORG', '位于', '北京', 'LOCATION', doc_id='A')
qh = storage.get_entity('清华大学')
check('同一文档重复写入count不累加', qh['count'] == 1, f"count={qh['count']}")
check('同一关系去重', len(storage.get_all_relations()) == 1)

# 模拟文档B：共享实体 北京，新增实体 北京大学
storage.add_entity('北京大学', 'ORG', doc_id='B')
storage.add_entity('北京', 'LOCATION', doc_id='B')
storage.add_relation('北京大学', 'ORG', '位于', '北京', 'LOCATION', doc_id='B')
bj = storage.get_entity('北京')
check('共享实体被两个文档引用count=2', bj['count'] == 2, f"count={bj['count']}")
check('共享实体doc_ids=[A,B]', set(bj['doc_ids']) == {'A', 'B'})
check('删除前实体总数=3', storage.get_statistics()['total_entities'] == 3)
check('删除前关系总数=2', storage.get_statistics()['total_relations'] == 2)

# 删除文档A
cleanup = storage.remove_document_data('A')
print('清理结果:', cleanup)
check('文档A删除时移除1条独有关系', cleanup['relations_removed'] == 1)
check('文档A删除时移除1个独有实体(清华)', cleanup['entities_removed'] == 1)
check('删除A后清华大学实体不存在', storage.get_entity('清华大学') is None)
check('共享实体北京保留', storage.get_entity('北京') is not None)
bj = storage.get_entity('北京')
check('共享实体北京doc_ids只剩B', bj['doc_ids'] == ['B'], f"doc_ids={bj['doc_ids']}")
check('共享实体count降为1', bj['count'] == 1)
check('北京大学实体保留', storage.get_entity('北京大学') is not None)
check('删除A后实体总数=2', storage.get_statistics()['total_entities'] == 2)
check('删除A后关系总数=1', storage.get_statistics()['total_relations'] == 1)

# 重新上传同一份文档A并解析，验证无重复节点
storage.add_entity('清华大学', 'ORG', doc_id='A')
storage.add_entity('北京', 'LOCATION', doc_id='A')
storage.add_relation('清华大学', 'ORG', '位于', '北京', 'LOCATION', doc_id='A')
qh = storage.get_entity('清华大学')
check('重新上传后清华实体唯一', len([e for e in storage.get_all_entities() if e['text'] == '清华大学']) == 1)
check('重新上传后北京实体唯一', len([e for e in storage.get_all_entities() if e['text'] == '北京']) == 1)
check('重新上传后关系唯一(不重复)',
      len([r for r in storage.get_all_relations()
           if r['subject'] == '清华大学' and r['object'] == '北京']) == 1)
check('重新上传后实体总数恢复=3', storage.get_statistics()['total_entities'] == 3)
check('重新上传后关系总数恢复=2', storage.get_statistics()['total_relations'] == 2)
check('重新生成的清华id与删除前不同(不与北大id碰撞)',
      qh['id'] != storage.get_entity('北京大学')['id'],
      f"清华={qh['id']} 北大={storage.get_entity('北京大学')['id']}")

# 手动标注数据不随文档删除
storage.add_entity('自定义实体', 'OTHER', {'manual': True})
storage.add_relation('自定义实体', 'OTHER', '相关', '北京', 'LOCATION',
                     {'manual': True})
before = storage.get_statistics()
storage.remove_document_data('B')
after = storage.get_statistics()
check('手动标注实体不被删除', storage.get_entity('自定义实体') is not None)
manual_rels = [r for r in storage.get_all_relations()
               if r.get('properties', {}).get('manual')]
check('手动标注关系不被删除', len(manual_rels) == 1)
# 手动关系引用的北京，在B被删后应保留（悬挂引用保护）
check('被手动关系引用的北京在文档全删后仍保留', storage.get_entity('北京') is not None)

# 验证落盘后重新加载，id仍唯一
storage2 = GraphStorage()
ids = [e['id'] for e in storage2.get_all_entities()]
check('落盘重载后实体id全局唯一', len(ids) == len(set(ids)), f"ids={ids}")

print(f"\n{'='*50}")
print(f"通过: {len(passed)}, 失败: {len(failed)}")
if failed:
    print('失败项:', failed)
    sys.exit(1)

shutil.rmtree(tmp_data, ignore_errors=True)
print("全部通过 ✅")
