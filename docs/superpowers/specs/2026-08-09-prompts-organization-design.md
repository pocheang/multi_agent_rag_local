# Prompt 目录整理设计

日期：2026-08-09

## 目标

将 `app/prompts` 按项目能力整理为可发现、可维护的目录结构，同时保留
现有 prompt 内容、运行时行为、历史 import 路径和 `PromptManager` 兼容性。

本次只整理 prompt 目录，不新增业务能力，不重写 prompt 文案，不改变模型
选择、调用顺序或生成结果格式。

## 最终目录

```text
app/prompts/
├── core/
│   ├── canonical_agent_prompts.py
│   ├── router_prompts.py
│   ├── intent_prompts.py
│   ├── synthesis_prompts.py
│   ├── review_prompts.py
│   └── react_prompts.py
├── retrieval/
│   ├── rag_quick_retrieval_prompts.py
│   └── self_rag_prompts.py
├── skills/
│   ├── ai_knowledge_prompts.py
│   ├── cybersecurity_skills_prompts.py
│   ├── comparison_timeline_prompts.py
│   └── pdf_web_prompts.py
├── manager.py
├── __init__.py
└── README.md
```

### `core/`

放置直接参与 Agent 执行的核心 prompt。`canonical_agent_prompts.py` 是
运行时唯一 canonical owner，包含 router、ReAct、synthesis/review 和 query
decomposition 的生产模板。

其他 core 文件保留现有 PromptManager 使用的专业化模板，不复制
`canonical_agent_prompts.py` 中的生产模板。

### `retrieval/`

放置向量检索、快速检索和 Self-RAG 评估相关 prompt。

### `skills/`

放置按业务技能划分的 prompt，包括 AI 知识、安全分析、对比/时间线、PDF
和 Web 事实核查。

### 根目录

`manager.py` 保留在根目录，作为历史统一管理入口；`__init__.py` 继续提供
现有公开导出；`README.md` 更新为完整目录、owner、生产调用关系和使用规范。

## 兼容策略

物理文件迁移后，原有根路径模块保留为无业务逻辑兼容导出，直到确认没有
生产、脚本、测试或文档调用者。兼容模块不得重新定义 prompt 内容。

以下现有入口必须保持可用：

- `from app.prompts import ...`
- `from app.prompts.canonical_agent_prompts import ...`
- `from app.prompts.react_prompts import ...`
- `from app.prompts.manager import PromptManager`
- 其他现有根 prompt 模块 import 路径

生产代码可以逐步切换到新的 canonical 子目录路径，但不要求本次删除历史
兼容入口。

## 迁移步骤

1. 重新搜索 `app`、`scripts`、`tests`、`docs` 和 `config` 中的 prompt import
   与动态加载路径。
2. 创建 `core`、`retrieval`、`skills` 子包及其 `__init__.py`。
3. 移动实际实现文件，并修正包内相对 import。
4. 将旧根路径缩减为无逻辑 re-export；不能留下第二份 prompt 文案。
5. 更新 `app/prompts/__init__.py` 的统一导出和 `README.md` 的模块说明。
6. 更新后端相关文档中的路径示例。
7. 对每个迁移文件执行迁移前后 import 搜索，记录保留兼容层的理由。

## 行为边界

必须保持：

- prompt 字符串内容完全不变
- 导出的常量名、函数名和返回值不变
- `PromptManager` 的 key、模板和访问方式不变
- 生产 Agent 的 prompt 来源不变，只改变文件路径
- HTTP、SSE、答案字段、引用格式和错误语义不受影响

## 验证

不修改或运行测试。实现后只运行静态和导入边界检查：

```text
conda run -n rag-local python -c "..."
conda run -n rag-local ruff check --select E9,F63,F7,F82 app
git diff --check
```

另外检查：

- 根路径兼容模块不包含 prompt 长字符串定义
- 每个 canonical prompt 只有一个运行时定义
- `app` 非 prompt 层不存在错误的 API 反向依赖
- 所有已知生产 prompt import 都能解析
