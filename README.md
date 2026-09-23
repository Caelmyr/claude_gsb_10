# 知识图谱构建与智能问答系统

一个完整的知识图谱构建与智能问答系统，支持文档上传、实体关系抽取、图谱可视化和多轮对话问答。

## 🚀 功能特性

### 1. 文档管理 (`index.html`)
- 支持上传 TXT 和 PDF 格式文档
- 自动提取文档文本内容
- 文档预览功能
- 一键解析文档并抽取实体关系

### 2. 实体关系标注 (`annotate.html`)
- 可视化文本选择标注
- 支持多种实体类型：人物、组织、地点、时间、概念
- 手动添加实体和关系
- 拖拽式交互体验

### 3. 知识图谱可视化 (`graph.html`)
- D3.js 力导向布局
- 节点可拖拽、缩放
- 按实体类型筛选
- 实体搜索功能
- 节点详情查看

### 4. 智能问答 (`chat.html`)
- 多轮对话支持
- 基于图谱的语义检索
- 会话管理和历史记录
- 快捷问题模板

### 5. 统计面板 (`stats.html`)
- 实体/关系数量统计
- 实体类型分布图表
- 关系类型分布图表
- 热门实体排行
- 最新三元组展示

## 📁 项目结构

```
knowledge_graph_qa/
├── backend/
│   ├── app.py              # Flask主应用
│   ├── nlp/
│   │   ├── tokenizer.py    # 中文分词
│   │   ├── ner.py          # 命名实体识别
│   │   ├── relation_extractor.py  # 关系抽取
│   │   └── pipeline.py     # NLP处理管道
│   ├── graph/
│   │   ├── builder.py      # 图谱构建
│   │   ├── query.py        # 图谱查询
│   │   └── storage.py      # 图谱存储（JSON分片）
│   ├── qa/
│   │   ├── retriever.py    # 语义检索
│   │   ├── dialogue.py     # 对话管理
│   │   └── generator.py    # 答案生成
│   └── utils/
│       ├── config.py       # 配置文件
│       └── text_extractor.py  # 文本提取
├── frontend/
│   ├── index.html          # 文档管理页面
│   ├── annotate.html       # 实体标注页面
│   ├── graph.html          # 图谱可视化页面
│   ├── chat.html           # 智能问答页面
│   └── stats.html          # 统计面板页面
├── data/
│   ├── documents/          # 上传文档存储
│   ├── triples/            # 三元组存储
│   ├── graph/              # 图谱分片存储
│   └── sessions/           # 会话历史存储
├── requirements.txt        # Python依赖
├── run.py                  # 启动脚本
└── README.md               # 项目说明
```

## 🛠️ 安装与运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动系统

```bash
python run.py
```

### 3. 访问系统

打开浏览器访问: http://localhost:5000

## 📖 使用指南

### 步骤1：上传文档
1. 访问首页（文档管理）
2. 点击上传区域或拖拽文件
3. 支持 TXT 和 PDF 格式

### 步骤2：解析文档
1. 在文档列表中点击"解析"按钮
2. 系统自动进行：
   - 中文分词
   - 命名实体识别
   - 关系抽取
   - 三元组生成

### 步骤3：查看图谱
1. 访问"知识图谱"页面
2. 查看力导向图谱可视化
3. 可拖拽节点、缩放、搜索

### 步骤4：智能问答
1. 访问"智能问答"页面
2. 创建新会话
3. 输入问题进行多轮对话

## 🔧 技术架构

### 后端技术栈
- **Web框架**: Flask
- **中文分词**: jieba
- **PDF解析**: pdfplumber
- **NLP**: 基于规则的NER和关系抽取

### 前端技术栈
- **图谱可视化**: D3.js v7
- **图表统计**: Chart.js
- **UI**: 原生HTML/CSS

### 数据存储
- 文档: JSON元数据 + 原始文件
- 三元组: JSON文件（按文档分文件）
- 图谱: JSON分片（按实体类型）
- 会话: JSON文件（按会话ID）

## 🎯 核心难点解决方案

### 1. NLP Pipeline准确性
- 结合jieba词性标注和正则模式
- 多种实体类型识别模式
- 上下文窗口辅助识别

### 2. 实体消歧与关系抽取
- 基于模式匹配的关系抽取
- 实体去重机制
- 置信度评估

### 3. 图谱查询索引优化
- 按实体类型分片存储
- 内存缓存加速查询
- 支持多跳路径查询

### 4. 多轮对话上下文管理
- 会话级上下文维护
- 最近N轮消息记忆
- 实体追踪与关联

### 5. JSON图谱增量更新
- 分片锁机制保证一致性
- 原子性写入操作
- 增量合并策略

## 📊 API接口

### 文档管理
- `POST /api/documents/upload` - 上传文档
- `GET /api/documents` - 获取文档列表
- `GET /api/documents/:id` - 获取文档详情
- `DELETE /api/documents/:id` - 删除文档（同步清理三元组及图谱中的实体/关系）
- `POST /api/documents/:id/parse` - 解析文档（重复解析幂等，不会造成计数累加）

### 图谱查询
- `GET /api/graph/data` - 获取图谱数据
- `GET /api/graph/statistics` - 获取统计信息
- `POST /api/graph/query` - 查询图谱
- `GET /api/graph/subgraph/:entity` - 获取子图

### 智能问答
- `POST /api/qa/ask` - 提问
- `GET /api/qa/sessions` - 获取会话列表
- `POST /api/qa/sessions` - 创建会话
- `GET /api/qa/sessions/:id/messages` - 获取消息

### 标注接口
- `POST /api/annotate/entity` - 标注实体
- `POST /api/annotate/relation` - 标注关系

## 📝 许可证

MIT License
