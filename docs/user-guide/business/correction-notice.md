# 文档修正说明

## ⚠️ 重要提示

当前 `docs/user-guide/business/` 目录下的非技术文档使用了**通用场景示例**（如产品价格查询、保修政策等），这些示例**不完全符合本项目的实际应用场景**。

## 本项目的实际定位

根据代码分析，本项目是一个**企业级多智能体RAG系统**，主要特点：

### 实际应用领域

1. **网络安全知识助手** (cybersecurity)
   - 攻击分析、漏洞研究
   - 防御加固、安全配置
   - 应急响应、事件处置
   - 威胁情报、攻防技术

2. **AI知识助手** (artificial_intelligence)
   - 人工智能、机器学习概念
   - 大模型、RAG技术
   - 提示词工程
   - AI系统架构

3. **PDF文档处理** (pdf_text)
   - PDF文字提取
   - OCR文字识别
   - 图片、图表处理
   - 文档内容分析

4. **通用知识查询** (general)
   - 其他领域的文档问答

### 实际的智能体技能

项目实际支持的技能（Skills）包括：

**网络安全技能**：
- `cyber_attack_analysis` - 网络攻击分析
- `cyber_defense_hardening` - 防御加固
- `incident_response_playbook` - 应急响应手册

**通用技能**：
- `answer_with_citations` - 带引用的答案
- `compare_entities` - 实体对比
- `timeline_builder` - 时间线构建
- `web_fact_check` - 网络事实核查
- `pdf_text_reader` - PDF文本阅读
- `ai_knowledge_assistant` - AI知识助手

### 实际的查询场景示例

**正确的示例**应该是：

```
问：什么是SQL注入攻击？
答：SQL注入是一种常见的Web应用漏洞...
来源：网络安全基础.pdf 第45页

问：如何防御勒索软件？
答：防御勒索软件的关键措施包括：
1. 定期备份数据
2. 部署EDR解决方案
3. 实施零信任架构
...
来源：企业安全加固指南.pdf 第12-15页

问：MITRE ATT&CK框架是什么？
答：MITRE ATT&CK是一个全球性的对抗战术、技术和常识库...
来源：威胁情报分析.pdf 第8页

问：什么是RAG技术？
答：RAG（检索增强生成）是一种结合信息检索和生成式AI的技术...
来源：大模型技术白皮书.pdf 第23页

问：如何从扫描的PDF中提取文字？
答：系统使用OCR技术自动识别图片中的文字...
来源：系统使用手册.pdf 第5页
```

**不正确的示例**（现有文档中使用的）：
```
❌ 问：产品A的价格是多少？
❌ 问：保修政策是什么？
❌ 问：如何申请差旅费报销？
```

## 建议的修正方案

### 方案1：修正现有文档（推荐）

将现有的非技术文档中的所有示例替换为网络安全/AI知识相关的场景：

**需要修正的文件**：
- `SYSTEM_OVERVIEW.md` - 修改示例场景
- `FEATURES.md` - 修改功能示例
- `HOW_IT_WORKS.md` - 修改完整流程示例
- `GLOSSARY.md` - 保持通用（术语表可以保留）

### 方案2：保留通用版本 + 添加实际案例

在每个文档中添加一个章节说明：
```markdown
## 关于示例

本文档使用通用场景示例便于理解。实际上，本系统专注于：
- 网络安全知识管理
- AI技术文档问答
- PDF文档智能处理

实际使用案例请参考：[实际应用案例](./features.md)
```

### 方案3：创建两套文档

- **通用版**：`docs/user-guide/business/` - 给非技术人员理解技术概念
- **实际版**：`docs/user-guide/use-cases/` - 具体的应用场景和示例

## 项目的实际技术特点

### 1. 多智能体协同

**实际的智能体**：
- Router Agent（路由智能体）- 判断问题类型（网络安全/AI/PDF/通用）
- Vector RAG Agent（向量检索智能体）- 语义搜索
- Graph RAG Agent（图检索智能体）- 关系查询
- Web Research Agent（网络研究智能体）- 网络查询
- Synthesis Agent（综合智能体）- 整合答案

### 2. 实际的路由决策

```python
问题类型判断：
- 包含"攻击"、"漏洞"、"防护" → cybersecurity类
  → 技能：cyber_attack_analysis / cyber_defense_hardening
  
- 包含"AI"、"机器学习"、"大模型" → artificial_intelligence类
  → 技能：ai_knowledge_assistant
  
- 包含"PDF"、"OCR"、"图片" → pdf_text类
  → 技能：pdf_text_reader
  
- 其他 → general类
  → 技能：answer_with_citations
```

### 3. 实际支持的文档类型

- ✅ PDF文档（带OCR）
- ✅ 图片（自动文字识别）
- ✅ 文本文件
- ✅ Word文档
- ✅ 网页内容（Web Research）

### 4. 实际的数据库使用

- **ChromaDB**：向量存储（语义搜索）
- **Neo4j**（可选）：知识图谱（实体关系）
- **SQLite**：用户、会话、文档元数据

### 5. 实际的模型支持

**本地模型（默认）**：
- Chat: `qwen2.5:7b-instruct`
- Embed: `nomic-embed-text`
- 通过Ollama运行

**云端模型（可选）**：
- OpenAI GPT-4/GPT-3.5
- Claude（Anthropic）

## 后续行动

请选择以下操作：

1. **修正所有示例** - 将所有文档中的示例改为网络安全/AI相关
2. **添加说明** - 在现有文档前添加免责说明
3. **创建实际案例文档** - 保留通用文档，另外创建实际应用案例
4. **不做修改** - 保留通用示例作为教学材料

---

**创建日期**: 2026-06-19  
**状态**: 待处理
