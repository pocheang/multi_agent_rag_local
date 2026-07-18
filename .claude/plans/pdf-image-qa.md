# PDF图片解析与问答功能计划

## 功能目标

实现对PDF文档中图片（图表、示意图、照片等）的智能解析和问答能力：
1. 自动提取PDF中的图片
2. 使用视觉模型理解图片内容
3. 将图片信息索引到知识库
4. 支持用户针对图片内容提问

**典型使用场景：**
- "这个报告中的销售趋势图显示了什么？"
- "PDF第5页的架构图有哪些组件？"
- "文档中所有的流程图都在描述什么？"

---

## 当前系统状态

### ✅ 已有能力
- **图表提取**：`pdf_chart_loader.py` - 使用vision模型（GPT-4o/Claude）从PDF提取图表
- **Vision模型配置**：config中已有 `pdf_chart_vision_model`, `openai_vision_model`, `ollama_vision_model`
- **图片OCR**：`image_loader.py` - Tesseract OCR提取图片中的文字
- **图表描述生成**：`chart_extractor.py` + `vision_utils.py` - 生成图表的文字描述

### ❌ 缺失能力
- 图片内容未被语义索引（仅OCR文字被索引）
- 无法回答关于图片视觉内容的问题（颜色、布局、趋势等）
- 图片与文本检索分离，答案中不引用图片
- 图片描述质量依赖OCR，视觉语义丢失

---

## 解决方案架构

### 核心思路：Vision-Enhanced Retrieval

```
PDF上传
  ↓
提取图片 (现有)
  ↓
生成视觉描述 (Vision Model) ← 新增增强
  ↓
嵌入到向量库 (Text Embedding)
  ↓
用户提问 → 检索相关图片描述 → 生成答案 + 引用图片
```

### 技术方案：利用现有Vision模型

**不引入新模型**，而是增强现有流程：
1. 使用已配置的GPT-4o/Claude Opus进行图片理解
2. 生成详细的图片描述（包含视觉特征、数据趋势、关键元素）
3. 将描述作为文本chunk索引到ChromaDB
4. 在答案中引用图片来源

---

## 实施计划（简化版）

### Phase 1: 增强图片描述生成 (1天)

**目标**：提升PDF图片的描述质量，使其包含更多可检索信息

**修改文件：**
1. [app/ingestion/loaders/pdf_chart_loader.py](app/ingestion/loaders/pdf_chart_loader.py)
   - 增强prompt：生成更详细的图片描述
   - 包含：图表类型、数据趋势、关键数值、视觉特征、布局信息

2. [app/ingestion/utils/vision_utils.py](app/ingestion/utils/vision_utils.py)
   - 改进 `describe_image()` 函数
   - 支持结构化描述输出

**新的描述格式示例：**
```
【图表类型】柱状图
【主题】2020-2023年季度销售额对比
【数据趋势】销售额逐年上升，2023Q4达到峰值5.2M
【关键观察】2022Q2有明显下降，可能受疫情影响
【视觉特征】蓝色系配色，带数据标签
【位置】报告第12页，第2.3节"业绩分析"
```

### Phase 2: 图片内容索引 (0.5天)

**目标**：将增强的图片描述索引到向量库

**修改文件：**
1. [app/services/ingest_service.py](app/services/ingest_service.py)
   - 确保图表documents被正确chunking和索引
   - 添加元数据：`{"type": "image", "image_type": "chart", "page": 12}`

2. [app/ingestion/chunker.py](app/ingestion/chunker.py)
   - 图片描述作为独立chunk，不与文本合并
   - 保留图片路径和页码信息

**数据流：**
```python
# 当前 (仅文字)
PDF → extract_text → chunk → embed → ChromaDB

# 新增 (文字+图片)
PDF → extract_text → chunk → embed → ChromaDB
    ↓
    extract_images → describe (vision) → chunk → embed → ChromaDB
                                                          ↑
                                                   (metadata: image_path)
```

### Phase 3: 图片引用与展示 (1天)

**目标**：在答案中引用和展示图片

**修改文件：**
1. [app/agents/synthesis_agent.py](app/agents/synthesis_agent.py)
   - 识别检索结果中的图片类型chunk
   - 在答案中生成图片引用：`![第12页销售图表](uploads/report_p12_chart.png)`

2. [app/api/routes/documents.py](app/api/routes/documents.py)
   - 添加 `GET /api/images/{image_id}` 端点服务图片

3. [frontend/src/pages/chat/components/MessageDisplay.tsx](frontend/src/pages/chat/components/MessageDisplay.tsx)
   - 渲染Markdown中的图片引用
   - 点击图片放大查看

### Phase 4: 配置与测试 (0.5天)

**新增配置项 (.env):**
```bash
# 已有配置（保持不变）
PDF_ENABLE_CHART_EXTRACTION=True
PDF_CHART_VISION_MODEL=gpt-4o

# 新增配置
PDF_IMAGE_DESCRIPTION_DETAIL=high  # low|medium|high
PDF_IMAGE_INDEX_ENABLED=True
PDF_IMAGE_DESCRIPTION_PROMPT=detailed  # brief|detailed|technical
```

**测试用例：**
1. 上传包含图表的PDF
2. 提问"文档中的趋势图显示了什么？"
3. 验证答案引用了正确的图片
4. 检查图片能否正常显示

---

## 详细实现示例

### 1. 增强的Vision Prompt

**当前prompt（简化）：**
```python
"Describe this chart briefly."
```

**新prompt（详细）：**
```python
"""
请详细分析这张图片，包含以下信息：

1. **图表类型**：（柱状图/折线图/饼图/流程图/架构图等）
2. **主题**：图片的主要内容是什么
3. **数据分析**：关键数据、趋势、对比（如有）
4. **视觉特征**：配色、标注、布局
5. **关键结论**：这张图想传达什么信息

请用结构化格式输出，便于检索。
"""
```

### 2. Chunk元数据结构

```python
{
    "id": "chunk_abc123",
    "text": "【图表类型】柱状图\n【主题】...",  # 视觉描述
    "metadata": {
        "source": "report.pdf",
        "page": 12,
        "type": "image",           # 新增
        "image_type": "chart",     # chart|diagram|photo
        "image_path": "uploads/report_p12_chart.png",  # 新增
        "chunk_id": "chunk_abc123",
        "has_visual_content": True  # 新增标记
    }
}
```

### 3. 答案引用示例

**用户提问：**
> "这份报告的销售趋势如何？"

**系统回答：**
```markdown
根据报告第12页的销售数据图表[图1]，2020-2023年呈现持续增长趋势：

- 2020年：3.2M
- 2021年：3.8M (+18.75%)
- 2022年：4.1M (+7.89%)
- 2023年：5.2M (+26.83%)

![销售趋势图](uploads/report_p12_chart.png)

特别值得注意的是2023年的增长加速，可能与新产品线推出有关（详见第15页）。

**数据来源：** [report.pdf:12]
```

---

## 性能与成本

### Vision API调用成本
- **GPT-4o:** ~$0.01/图片（高质量）
- **Claude Opus:** ~$0.015/图片（更详细）
- **频率：** 仅在文档上传时调用，查询时不产生额外成本

### 存储开销
- 每张图片描述：~500-1000字符
- 100个PDF × 平均5张图/PDF = 500张图 → ~500KB文本 + 500×2KB向量 = 1.5MB

### 延迟影响
- **上传阶段：** +2-5秒/图片（vision API调用）
- **查询阶段：** 无额外延迟（与文本检索相同）

---

## 优势与限制

### ✅ 优势
1. **无需新模型**：复用已配置的GPT-4o/Claude
2. **无缝集成**：利用现有向量检索架构
3. **向后兼容**：通过feature flag控制
4. **即时生效**：无需重新训练或部署新模型

### ⚠️ 限制
1. **依赖外部API**：需要OpenAI/Anthropic API密钥
2. **上传速度**：图片多的PDF处理变慢
3. **描述质量**：受限于vision模型能力
4. **成本**：大量PDF上传会产生API费用

---

## 成功标准

✅ **功能完整性**
- [ ] PDF上传时自动提取并描述所有图片
- [ ] 用户可以通过自然语言查询图片内容
- [ ] 答案中正确引用图片来源
- [ ] 前端能展示引用的图片

✅ **质量指标**
- [ ] 图片描述准确率 >85%（人工抽查）
- [ ] 图片相关问题召回率 >75%（包含正确图片）
- [ ] 用户满意度 >4/5分

✅ **性能指标**
- [ ] 单张图片描述生成 <5秒
- [ ] 查询延迟无明显增加 (<100ms)

---

## 下一步

请您确认以下问题：

1. **Vision模型选择**：使用GPT-4o（快速）还是Claude Opus（详细）？
2. **描述详细度**：简要描述（fast）还是详细分析（thorough）？
3. **启用范围**：
   - [ ] 仅图表（chart/graph）
   - [ ] 所有图片（chart + photo + diagram）
4. **批量重索引**：是否需要对现有PDF重新处理？

确认后我将开始Phase 1的实施。
