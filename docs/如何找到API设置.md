# 如何找到 API 设置

## 访问地址

登录后进入主应用：

```text
http://localhost:8000/app
```

如果使用 Vite 开发服务，也可以访问：

```text
http://localhost:5173/app
```

> Host consistency tip: keep the frontend host and API host the same (`localhost` with `localhost`, or `127.0.0.1` with `127.0.0.1`) to avoid login cookie issues.

## 设置按钮位置

1. 登录系统。
2. 进入 `Agentic RAG Studio` 主聊天界面。
3. 在顶部操作区点击 `设置` 按钮。
4. 右侧会打开 `模型 API 设置` 面板。

## 普通用户可以设置什么

- `Provider`：Ollama、OpenAI、DeepSeek、Anthropic、Custom
- `API Key`：云端模型提供商的密钥
- `Base URL`：模型服务地址
- `Model`：聊天/推理模型名称
- `Temperature`：输出随机性
- `Max Tokens`：最大输出长度

保存后，新的问答请求会读取当前用户保存的聊天模型 API 设置。

## Embedding 和索引设置在哪里

Embedding 不是普通用户级设置，而是管理员级全局配置。原因是向量索引必须使用一致的 embedding 模型写入和检索；如果不同用户随意切换 embedding 并写入同一个向量库，容易产生维度不一致、召回失真和缓存污染。

管理员可以在后台的模型设置中配置全局 embedding 模型。修改 embedding 模型后，建议重建索引，让 Chroma 向量库、BM25 语料和图谱数据保持一致。

## 如果找不到设置按钮

1. 确认访问的是 `/app`。
2. 确认已经登录。
3. 如果窗口较窄，先点击顶部的 `菜单` 或放大窗口。
4. 如果接口报错，确认后端 `http://localhost:8000` 正在运行。
