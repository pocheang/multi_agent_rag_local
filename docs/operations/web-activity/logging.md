# Web Activity Logging & Analytics System

**版本**: v1.0  
**创建日期**: 2026-06-30  
**用途**: 管理层监控用户Web搜索行为和访问网站统计

---

## 📋 系统概述

本系统为管理层提供完整的Web搜索活动监控和分析能力，包括：

- ✅ **活动日志记录** - 自动记录每次Web搜索
- ✅ **统计数据聚合** - 实时分析和统计
- ✅ **管理API接口** - RESTful API访问
- ✅ **可视化Dashboard** - 图表和报表展示

---

## 🏗️ 系统架构

```
用户查询
    ↓
Web Research Agent
    ↓
[活动日志记录] → logs/web_activity/web_activity_YYYYMMDD.jsonl
    ↓
[统计分析器] → 聚合统计数据
    ↓
[管理API] → 提供数据接口
    ↓
[前端Dashboard] → 可视化展示
```

---

## 📁 文件结构

```
app/
├── agents/
│   ├── web_research_agent.py          # Web搜索Agent（已集成日志）
│   ├── web_activity_logger.py         # 活动日志记录器
│   └── web_research_utils.py          # 工具函数
├── api/
│   └── routes/
│       └── web_activity_admin.py      # 管理API路由
└── static/
    └── web_activity_dashboard.html    # 前端仪表板

logs/
└── web_activity/
    ├── web_activity_20260630.jsonl    # 每日日志文件
    ├── web_activity_20260629.jsonl
    └── ...
```

---

## 🚀 快速开始

### 1. 注册API路由

在 `app/api/main.py` 中添加：

```python
from app.api.routes import web_activity_admin

# 注册路由
app.include_router(web_activity_admin.router)
```

### 2. 启动服务

```bash
# 激活conda环境
conda activate rag-local

# 启动API服务
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 访问Dashboard

打开浏览器访问：
```
http://localhost:8000/static/web_activity_dashboard.html
```

或通过API访问：
```
http://localhost:8000/api/v1/admin/web-activity/dashboard
```

---

## 📊 功能详解

### 1. 活动日志记录

**自动记录内容**：

每次Web搜索会自动记录以下信息：

```json
{
  "timestamp": "2026-06-30T14:30:25.123456",
  "user_id": "user123",
  "session_id": "sess456",
  "query": "What is RAG in AI?",
  "query_sanitized": false,
  "search_success": true,
  "results_count": 5,
  "websites_accessed": [
    {
      "domain": "github.com",
      "url": "https://github.com/example/rag",
      "score": 0.8
    }
  ],
  "metrics": {
    "search_time": 1.23,
    "filter_time": 0.15,
    "total_results": 5,
    "filtered_results": 0,
    "final_results": 5
  },
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0..."
}
```

**日志文件**：

- 存储位置：`logs/web_activity/`
- 文件格式：JSONL（每行一条JSON记录）
- 文件命名：`web_activity_YYYYMMDD.jsonl`
- 按天分割，便于管理和归档

### 2. 统计数据聚合

**WebActivityAnalyzer** 提供以下统计：

#### 总体统计
- 总搜索次数
- 成功搜索次数和成功率
- 脱敏查询数量
- 独立用户数
- 访问的独立网站数
- 平均查询长度
- 平均搜索耗时

#### 网站统计
- 最常访问的网站（Top 20）
- 每个网站的访问次数
- 每个网站的平均信任度评分

#### 用户统计
- 最活跃用户（Top 10）
- 每个用户的搜索次数

#### 时间分布
- 24小时活动分布
- 每小时的搜索次数

---

## 🔌 API接口文档

### 基础URL
```
http://localhost:8000/api/v1/admin/web-activity
```

### 1. 获取统计摘要

**端点**: `GET /stats`

**参数**:
- `start_date` (可选): 开始日期 (YYYY-MM-DD)
- `end_date` (可选): 结束日期 (YYYY-MM-DD)
- `user_id` (可选): 筛选特定用户

**示例请求**:
```bash
curl "http://localhost:8000/api/v1/admin/web-activity/stats?start_date=2026-06-23&end_date=2026-06-30"
```

**返回示例**:
```json
{
  "summary": {
    "total_searches": 150,
    "successful_searches": 135,
    "success_rate": 90.0,
    "sanitized_queries": 5,
    "unique_users": 25,
    "unique_websites": 45,
    "avg_query_length": 35.5,
    "avg_search_time": 1.8
  },
  "top_websites": [
    {
      "domain": "github.com",
      "visit_count": 45,
      "avg_trust_score": 0.8
    }
  ],
  "top_users": [
    {
      "user_id": "user123",
      "search_count": 28
    }
  ],
  "hourly_distribution": {
    "0": 2,
    "1": 1,
    ...
  }
}
```

### 2. 生成分析报告

**端点**: `GET /report`

**参数**:
- `start_date` (可选): 开始日期
- `end_date` (可选): 结束日期
- `format` (可选): 输出格式 (text/json/html)，默认html

**示例请求**:
```bash
# HTML报告
curl "http://localhost:8000/api/v1/admin/web-activity/report?format=html" > report.html

# JSON数据
curl "http://localhost:8000/api/v1/admin/web-activity/report?format=json"

# 文本报告
curl "http://localhost:8000/api/v1/admin/web-activity/report?format=text"
```

### 3. 查看原始日志

**端点**: `GET /logs`

**参数**:
- `start_date` (可选): 开始日期
- `end_date` (可选): 结束日期
- `user_id` (可选): 筛选用户
- `limit` (可选): 返回记录数，默认100，最大1000
- `offset` (可选): 跳过记录数，默认0

**示例请求**:
```bash
curl "http://localhost:8000/api/v1/admin/web-activity/logs?limit=50&offset=0"
```

### 4. 最常访问网站

**端点**: `GET /top-websites`

**参数**:
- `start_date` (可选): 开始日期
- `end_date` (可选): 结束日期
- `limit` (可选): 返回数量，默认20，最大100

**示例请求**:
```bash
curl "http://localhost:8000/api/v1/admin/web-activity/top-websites?limit=10"
```

### 5. 最活跃用户

**端点**: `GET /top-users`

**参数**:
- `start_date` (可选): 开始日期
- `end_date` (可选): 结束日期
- `limit` (可选): 返回数量，默认20，最大100

**示例请求**:
```bash
curl "http://localhost:8000/api/v1/admin/web-activity/top-users?limit=10"
```

### 6. 小时分布

**端点**: `GET /hourly-distribution`

**参数**:
- `start_date` (可选): 开始日期
- `end_date` (可选): 结束日期

**示例请求**:
```bash
curl "http://localhost:8000/api/v1/admin/web-activity/hourly-distribution"
```

### 7. 导出数据

**端点**: `GET /export`

**参数**:
- `start_date` (可选): 开始日期
- `end_date` (可选): 结束日期
- `format` (可选): 导出格式 (csv/json)，默认csv

**示例请求**:
```bash
# 导出CSV
curl "http://localhost:8000/api/v1/admin/web-activity/export?format=csv" > export.csv

# 导出JSON
curl "http://localhost:8000/api/v1/admin/web-activity/export?format=json" > export.json
```

### 8. 仪表板页面

**端点**: `GET /dashboard`

**参数**:
- `days` (可选): 显示最近几天的数据，默认7天，最大90天

**访问方式**:
```bash
# 浏览器访问
http://localhost:8000/api/v1/admin/web-activity/dashboard?days=7
```

---

## 📱 前端Dashboard使用指南

### 功能特性

1. **实时统计卡片**
   - 总搜索次数
   - 成功率
   - 独立用户数
   - 访问网站数

2. **交互式图表**
   - 24小时活动分布（折线图）
   - 最常访问网站（柱状图）
   - 最活跃用户（柱状图）

3. **数据表格**
   - 网站访问详情
   - 信任度评分标签

4. **控制功能**
   - 时间范围筛选（1天/7天/30天/90天）
   - 用户ID筛选
   - 一键刷新数据
   - 导出HTML报告

5. **自动刷新**
   - 每30秒自动更新数据
   - 显示最后更新时间

### 操作步骤

1. **选择时间范围**：从下拉菜单选择1天、7天、30天或90天

2. **筛选用户**：（可选）输入用户ID查看特定用户的活动

3. **刷新数据**：点击"🔄 刷新数据"按钮手动更新

4. **导出报告**：点击"📥 导出报告"生成HTML报告

5. **查看详情**：
   - 鼠标悬停在图表上查看具体数值
   - 滚动查看完整的网站访问表格

---

## 💻 编程接口使用

### Python示例

#### 1. 手动记录活动

```python
from app.agents.web_activity_logger import get_activity_logger

logger = get_activity_logger()

# 记录一次搜索
logger.log_search(
    user_id="user123",
    session_id="sess456",
    query="What is RAG?",
    query_sanitized=False,
    result={
        "used": True,
        "citations": [...],
        "metrics": {...}
    },
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0..."
)
```

#### 2. 查询日志

```python
from datetime import datetime, timedelta
from app.agents.web_activity_logger import get_activity_logger

logger = get_activity_logger()

# 获取最近7天的日志
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

logs = logger.get_logs(
    start_date=start_date,
    end_date=end_date,
    user_id="user123"  # 可选
)

print(f"找到 {len(logs)} 条日志")
```

#### 3. 生成统计分析

```python
from datetime import datetime, timedelta
from app.agents.web_activity_logger import get_activity_analyzer

analyzer = get_activity_analyzer()

# 分析最近7天的数据
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

analysis = analyzer.analyze(
    start_date=start_date,
    end_date=end_date
)

print(f"总搜索次数: {analysis['summary']['total_searches']}")
print(f"成功率: {analysis['summary']['success_rate']}%")
print(f"最常访问网站: {analysis['top_websites'][0]['domain']}")
```

#### 4. 生成报告

```python
from app.agents.web_activity_logger import get_activity_analyzer

analyzer = get_activity_analyzer()

# 生成HTML报告
html_report = analyzer.generate_report(output_format="html")
with open("report.html", "w", encoding="utf-8") as f:
    f.write(html_report)

# 生成文本报告
text_report = analyzer.generate_report(output_format="text")
print(text_report)

# 生成JSON数据
json_report = analyzer.generate_report(output_format="json")
```

---

## 🔒 安全和隐私

### 自动脱敏

系统会自动检测并移除敏感信息：
- Email地址 → `[REDACTED_EMAIL]`
- IP地址 → `[REDACTED_IP]`
- 密码 → `password=[REDACTED]`
- API密钥 → `api_key=[REDACTED]`
- 社会安全号 → `[REDACTED_SSN]`
- 信用卡号 → `[REDACTED_CARD]`

### 访问控制建议

1. **API访问**：建议添加认证中间件
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_admin(token = Depends(security)):
    # 验证token
    if not is_admin(token):
        raise HTTPException(status_code=403, detail="Admin access required")
    return token

# 应用到路由
@router.get("/stats", dependencies=[Depends(verify_admin)])
async def get_stats(...):
    ...
```

2. **Dashboard访问**：建议配置Nginx反向代理，添加HTTP Basic Auth

3. **日志文件**：设置适当的文件权限
```bash
chmod 750 logs/web_activity
chmod 640 logs/web_activity/*.jsonl
```

---

## 📈 性能和存储

### 日志文件大小

- 每条日志约 500-1000 字节
- 1000次搜索约 0.5-1 MB
- 建议定期归档超过30天的日志

### 存储管理

```bash
# 压缩旧日志
gzip logs/web_activity/web_activity_202606*.jsonl

# 清理超过90天的日志
find logs/web_activity -name "*.jsonl" -mtime +90 -delete
```

### 性能优化

1. **日志写入**：异步写入，不影响搜索性能
2. **数据读取**：缓存统计结果（建议使用Redis）
3. **大数据量**：考虑迁移到时序数据库（InfluxDB）

---

## 🛠️ 故障排查

### 问题1：日志文件未生成

**检查**：
```bash
ls -la logs/web_activity/
```

**解决**：
```bash
# 创建目录
mkdir -p logs/web_activity
chmod 750 logs/web_activity
```

### 问题2：Dashboard无法加载数据

**检查API**：
```bash
curl http://localhost:8000/api/v1/admin/web-activity/stats
```

**可能原因**：
- API服务未启动
- 路由未注册
- CORS配置问题

**解决**：
```python
# 在 main.py 中添加CORS
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 问题3：统计数据不准确

**检查日志格式**：
```bash
head -1 logs/web_activity/web_activity_$(date +%Y%m%d).jsonl | python -m json.tool
```

**验证记录**：
```python
from app.agents.web_activity_logger import get_activity_logger

logger = get_activity_logger()
logs = logger.get_logs()
print(f"总记录数: {len(logs)}")
```

---

## 📝 最佳实践

### 1. 定期备份

```bash
# 每周备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d)
tar -czf /backup/web_activity_$DATE.tar.gz logs/web_activity/
find /backup -name "web_activity_*.tar.gz" -mtime +90 -delete
```

### 2. 监控和告警

```python
# 定期检查异常
from app.agents.web_activity_logger import get_activity_analyzer

analyzer = get_activity_analyzer()
analysis = analyzer.analyze()

# 告警阈值
if analysis['summary']['success_rate'] < 80:
    send_alert("Web search success rate is low!")

if analysis['summary']['sanitized_queries'] > 10:
    send_alert("High number of sanitized queries detected!")
```

### 3. 数据清理

```python
# 每月运行
import os
from datetime import datetime, timedelta

cutoff_date = datetime.now() - timedelta(days=90)
log_dir = "logs/web_activity"

for filename in os.listdir(log_dir):
    if filename.endswith(".jsonl"):
        date_str = filename.replace("web_activity_", "").replace(".jsonl", "")
        file_date = datetime.strptime(date_str, "%Y%m%d")
        if file_date < cutoff_date:
            os.remove(os.path.join(log_dir, filename))
            print(f"Deleted old log: {filename}")
```

---

## 🎉 总结

### 已实现功能

✅ **活动日志记录**
- 自动记录每次Web搜索
- 详细的元数据（用户、时间、网站、性能）
- 敏感信息自动脱敏

✅ **统计分析**
- 实时统计聚合
- 多维度分析（时间、用户、网站）
- 灵活的查询和筛选

✅ **管理API**
- 8个RESTful API端点
- 支持多种输出格式
- 完整的参数验证

✅ **可视化Dashboard**
- 实时更新的统计卡片
- 交互式图表（Chart.js）
- 响应式设计
- 数据导出功能

### 适用场景

- 🏢 **企业管理**：监控员工搜索行为
- 📊 **数据分析**：了解用户兴趣和需求
- 🔒 **安全审计**：追踪敏感查询和访问
- 📈 **性能优化**：分析搜索模式，优化系统

---

**文档版本**: v1.0  
**最后更新**: 2026-06-30  
**维护者**: AI Assistant (Claude)
