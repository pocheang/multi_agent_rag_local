# Docling Integration - PDF表格处理增强

## 概述

Docling是IBM开源的文档转换工具，能够将PDF转换为Markdown格式，**保留表格结构**。这对知识图谱提取非常重要，因为表格中的结构化信息可以生成高质量的三元组。

## 为什么需要Docling？

### 传统方式的问题

使用PyPDF提取PDF时：
- **表格结构丢失**：表格被当成普通文本，行列关系混乱
- **三元组提取质量差**：无法理解哪些数据属于同一行
- **关系推断错误**：可能把不相关的实体连接起来

### Docling的优势

- ✅ **保留表格结构**：转换为Markdown表格格式
- ✅ **LLM友好**：大语言模型天然理解Markdown表格
- ✅ **提取质量高**：能根据列名生成准确的关系类型
- ✅ **支持复杂PDF**：处理多列布局、嵌套表格、公式等

## 配置方式

在 `.env` 文件中设置：

```bash
# PDF加载模式
PDF_LOADER_MODE=docling  # pypdf|docling|hybrid
```

### 三种模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **pypdf** (默认) | 使用PyPDF提取文本 + OCR提取图片 | 简单PDF，无复杂表格 |
| **docling** | 使用Docling转Markdown | 包含大量表格的PDF |
| **hybrid** | Docling提取文本 + OCR提取图片 | 既有表格又有图片的PDF |

## 使用示例

### 1. 测试Docling加载器

```bash
conda activate rag-local
python scripts/dev/test_docling_loader.py data/docs/your_file.pdf
```

这会显示：
- Docling提取的内容预览
- 是否检测到Markdown表格
- 与PyPDF的对比

### 2. 上传PDF并索引

启用Docling模式后，正常上传PDF即可：

```bash
# 设置环境变量
export PDF_LOADER_MODE=docling

# 启动服务
python -m uvicorn app.api.main:app --reload
```

通过API上传PDF：
```bash
curl -X POST "http://localhost:8000/api/documents/upload" \
  -F "file=@report.pdf"
```

### 3. 查看提取效果

上传后，系统会：
1. 用Docling将PDF转为Markdown
2. 保留表格结构（`| 列1 | 列2 |` 格式）
3. LLM提取三元组时能理解表格关系
4. 生成高质量的知识图谱

## 表格处理示例

### 原始PDF表格

```
┌──────────┬────────────┬───────────┐
│ 产品名称  │ 使用技术    │ 开发公司   │
├──────────┼────────────┼───────────┤
│ ChatGPT  │ GPT-4      │ OpenAI    │
│ Claude   │ Claude-3   │ Anthropic │
└──────────┴────────────┴───────────┘
```

### Docling转换后（Markdown）

```markdown
| 产品名称 | 使用技术 | 开发公司 |
|---------|---------|---------|
| ChatGPT | GPT-4   | OpenAI  |
| Claude  | Claude-3| Anthropic|
```

### LLM提取的三元组

```python
[
  {"head": "ChatGPT", "relation": "USES_TECHNOLOGY", "tail": "GPT-4"},
  {"head": "ChatGPT", "relation": "DEVELOPED_BY", "tail": "OpenAI"},
  {"head": "Claude", "relation": "USES_TECHNOLOGY", "tail": "Claude-3"},
  {"head": "Claude", "relation": "DEVELOPED_BY", "tail": "Anthropic"}
]
```

### 传统PyPDF提取（对比）

提取的文本可能是：
```
产品名称 使用技术 开发公司 ChatGPT GPT-4 OpenAI Claude Claude-3 Anthropic
```

提取的三元组（错误）：
```python
[
  {"head": "ChatGPT", "relation": "RELATED_TO", "tail": "Claude-3"},  # ❌ 错误关联
  {"head": "产品名称", "relation": "IS", "tail": "ChatGPT"}  # ❌ 无意义
]
```

## 性能考虑

### 速度对比

- **PyPDF**: 快速，适合大批量处理
- **Docling**: 较慢（使用深度学习模型），但质量高

### 建议

1. **开发/测试阶段**：使用 `docling` 模式，确保表格正确提取
2. **生产环境**：
   - 如果PDF主要是文本：使用 `pypdf`
   - 如果PDF包含重要表格：使用 `docling` 或 `hybrid`
3. **混合策略**：让用户上传时选择模式

## 故障排除

### Docling加载失败

如果Docling失败，系统会自动回退到PyPDF：

```python
# 代码中的自动回退逻辑
docling_docs = load_pdf_with_docling(path)
if docling_docs:
    return docling_docs
# 自动回退
return load_pdf_text(path)
```

### 检查Docling是否安装

```bash
conda activate rag-local
python -c "import docling; print('Docling installed:', docling.__version__)"
```

### 常见问题

**Q: Docling处理速度慢？**
A: Docling使用深度学习模型，首次运行会下载模型。后续会快很多。

**Q: 某些表格还是识别不准？**
A: 复杂表格（跨行跨列、嵌套）可能需要手动转换为Markdown后上传。

**Q: 如何只对特定PDF使用Docling？**
A: 目前是全局配置。未来可以添加per-file配置。

## 技术细节

### 代码位置

- **Docling加载器**: `app/ingestion/loaders/pdf_loader.py`
- **主加载逻辑**: `app/ingestion/loaders.py`
- **配置**: `app/core/config.py`
- **测试脚本**: `scripts/dev/test_docling_loader.py`

### 工作流程

```
PDF文件
  ↓
[Docling DocumentConverter]
  ↓
Markdown格式（保留表格）
  ↓
[LangChain Document对象]
  ↓
[文本分块]
  ↓
[三元组提取] ← LLM能理解Markdown表格
  ↓
[Neo4j图数据库]
```

## 下一步

1. ✅ Docling已集成
2. ⏳ 添加per-file配置（让用户选择模式）
3. ⏳ 优化Docling提示词（针对表格优化三元组提取）
4. ⏳ 添加表格质量检测（自动判断是否需要Docling）

## 参考资源

- [Docling GitHub](https://github.com/DS4SD/docling)
- [Docling文档](https://ds4sd.github.io/docling/)
- IBM Research论文
