# 监控系统部署指南
# Monitoring System Deployment Guide

本指南描述如何部署和配置完整的监控系统（Prometheus + Grafana + Alertmanager）。

This guide describes how to deploy and configure the complete monitoring stack.

---

## 📋 前置要求 / Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 至少2GB可用内存
- 端口可用：3000 (Grafana), 9090 (Prometheus), 9093 (Alertmanager)

---

## 🚀 快速开始 / Quick Start

### 1. 启动监控栈

```bash
# 启动所有监控服务
docker-compose -f docker-compose.monitoring.yml up -d

# 查看服务状态
docker-compose -f docker-compose.monitoring.yml ps

# 查看日志
docker-compose -f docker-compose.monitoring.yml logs -f
```

### 2. 访问服务

- **Grafana:** http://localhost:3000
  - 默认用户名: `admin`
  - 默认密码: `admin123`
  
- **Prometheus:** http://localhost:9090

- **Alertmanager:** http://localhost:9093

### 3. 验证监控

```bash
# 检查Prometheus targets
curl http://localhost:9090/api/v1/targets

# 检查是否能抓取RAG API指标
curl http://localhost:9090/api/v1/query?query=up{job="rag-api"}

# 检查告警规则
curl http://localhost:9090/api/v1/rules
```

---

## 📊 Grafana配置

### 导入仪表盘

1. 登录Grafana (http://localhost:3000)
2. 点击左侧菜单 "+" → "Import"
3. 上传 `dashboards/grafana/rag-system-overview.json`
4. 选择 "Prometheus" 作为数据源
5. 点击 "Import"

### 仪表盘面板说明

| 面板名称 | 描述 | 关键阈值 |
|---------|------|---------|
| System Health Status | 系统整体健康状态 | 0=DOWN, 1=HEALTHY |
| Total Query Rate | 总查询速率 | >100 qps 需要扩容 |
| Overall Success Rate | 整体成功率 | <95% 触发告警 |
| P95 Query Latency | 95分位延迟 | >4s 触发告警 |
| Agent Execution Rate | 各Agent执行速率 | 监控趋势 |
| Retrieval Quality Score | 检索质量分数 | <0.6 需要优化 |
| Cache Hit Rate | 缓存命中率 | <50% 需要优化 |
| LLM API Cost | LLM API成本 | >$20/h 触发告警 |
| Circuit Breaker Status | 熔断器状态 | OPEN=故障 |

---

## 🔔 告警配置

### Prometheus告警规则

告警规则已在 `config/prometheus/alert_rules.yml` 中定义：

**Critical级别 (立即处理):**
- SystemUnhealthy - 系统宕机
- HighAgentErrorRate - Agent错误率>10%
- LLMCostExceeded - LLM成本>$20/h
- AllCircuitBreakersOpen - 多个熔断器打开

**Warning级别 (需要关注):**
- HighLatency - P95延迟>4s
- LowRetrievalQuality - 检索质量<0.6
- LowCacheHitRate - 缓存命中率<50%
- CircuitBreakerOpen - 单个熔断器打开

**Info级别 (信息通知):**
- HighQueryRate - 查询速率高（可能需要扩容）
- LLMCostIncreasing - LLM成本上升
- LongUserSessions - 用户会话时长长（正常）

### 配置Slack通知

编辑 `config/alertmanager/alertmanager.yml`：

```yaml
receivers:
  - name: 'critical-alerts'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#rag-critical'
        title: '🚨 Critical Alert: {{ .GroupLabels.alertname }}'
```

### 配置PagerDuty

```yaml
receivers:
  - name: 'critical-alerts'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_SERVICE_KEY'
        description: '{{ .GroupLabels.alertname }}: {{ .Annotations.summary }}'
```

### 配置邮件通知

```yaml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'po.cheang@gmail.com'
  smtp_auth_username: 'your-email@gmail.com'
  smtp_auth_password: 'your-app-password'

receivers:
  - name: 'critical-alerts'
    email_configs:
      - to: 'po.cheang@gmail.com'
        subject: '🚨 CRITICAL: {{ .GroupLabels.alertname }}'
```

---

## 🔧 生产环境配置

### 1. 数据持久化

默认配置已启用持久化卷：

```yaml
volumes:
  prometheus_data:  # Prometheus数据（30天保留）
  grafana_data:     # Grafana配置和仪表盘
  alertmanager_data: # Alertmanager状态
```

### 2. 资源限制

在 `docker-compose.monitoring.yml` 中添加资源限制：

```yaml
services:
  prometheus:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### 3. 安全配置

#### 修改Grafana密码

```bash
# 方式1：环境变量
export GF_SECURITY_ADMIN_PASSWORD=your-secure-password

# 方式2：在docker-compose.yml中修改
environment:
  - GF_SECURITY_ADMIN_PASSWORD=your-secure-password
```

#### 启用HTTPS

```yaml
grafana:
  environment:
    - GF_SERVER_PROTOCOL=https
    - GF_SERVER_CERT_FILE=/etc/grafana/ssl/cert.pem
    - GF_SERVER_CERT_KEY=/etc/grafana/ssl/key.pem
  volumes:
    - ./ssl:/etc/grafana/ssl:ro
```

### 4. 备份配置

```bash
# 备份Prometheus数据
docker run --rm -v prometheus_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/prometheus-backup-$(date +%Y%m%d).tar.gz /data

# 备份Grafana配置
docker run --rm -v grafana_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/grafana-backup-$(date +%Y%m%d).tar.gz /data
```

---

## 📈 监控最佳实践

### 1. 设置合理的告警阈值

```yaml
# 根据实际负载调整
- alert: HighQueryRate
  expr: sum(rate(agent_execution_total[5m])) > 100  # 调整此值
  
- alert: HighLatency
  expr: histogram_quantile(0.95, ...) > 4  # 根据SLA调整
```

### 2. 告警疲劳预防

- 使用 `for` 子句避免瞬时抖动
- 设置合理的 `repeat_interval`
- 使用 `inhibit_rules` 抑制次要告警

### 3. 仪表盘组织

- **Overview** - 高层次KPI（已提供）
- **Agent Details** - 单个Agent深度分析
- **Infrastructure** - 基础设施指标
- **Cost Analysis** - 成本分析

### 4. 查询性能优化

```promql
# ❌ 慢查询
rate(agent_execution_total[5m])

# ✅ 快查询（预聚合）
sum(rate(agent_execution_total[5m])) by (agent)
```

---

## 🐛 故障排查

### Prometheus无法抓取指标

```bash
# 1. 检查RAG API是否运行
curl http://localhost:8000/metrics

# 2. 检查Prometheus配置
docker exec rag-prometheus cat /etc/prometheus/prometheus.yml

# 3. 查看Prometheus日志
docker logs rag-prometheus

# 4. 检查网络连接（Docker Desktop使用host.docker.internal）
docker exec rag-prometheus ping host.docker.internal
```

### Grafana无法连接Prometheus

```bash
# 1. 检查数据源配置
curl http://localhost:3000/api/datasources

# 2. 测试连接
docker exec rag-grafana wget -O- http://prometheus:9090/api/v1/query?query=up

# 3. 检查网络
docker network inspect monitoring_monitoring
```

### 告警未触发

```bash
# 1. 检查告警规则加载
curl http://localhost:9090/api/v1/rules

# 2. 验证告警表达式
curl 'http://localhost:9090/api/v1/query?query=YOUR_ALERT_EXPR'

# 3. 查看Alertmanager日志
docker logs rag-alertmanager

# 4. 测试告警发送
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"TestAlert"}}]'
```

---

## 📊 示例查询 / Example Queries

### Agent性能分析

```promql
# Top 5最慢的Agent（P95延迟）
topk(5,
  histogram_quantile(0.95,
    sum(rate(agent_duration_seconds_bucket[5m])) by (agent, le)
  )
)

# Agent错误率排名
topk(5,
  sum(rate(agent_execution_total{status="failed"}[5m])) by (agent)
  /
  sum(rate(agent_execution_total[5m])) by (agent)
)
```

### 成本分析

```promql
# 每日LLM成本预估
sum(increase(llm_api_cost_usd_total[24h]))

# 按模型的成本占比
sum(llm_api_cost_usd_total) by (model)
/
sum(llm_api_cost_usd_total)
```

### 容量规划

```promql
# 每秒查询数趋势（7天）
sum(rate(agent_execution_total[7d]))

# 预测未来容量需求（线性回归）
predict_linear(
  sum(rate(agent_execution_total[1h]))[7d:1h],
  7*24*3600  # 预测7天后
)
```

---

## 🔄 更新和维护

### 更新监控栈

```bash
# 拉取最新镜像
docker-compose -f docker-compose.monitoring.yml pull

# 重启服务
docker-compose -f docker-compose.monitoring.yml up -d
```

### 清理旧数据

```bash
# Prometheus数据默认保留30天
# 手动清理（谨慎操作）
docker exec rag-prometheus rm -rf /prometheus/*

# Grafana仪表盘导出备份
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:3000/api/dashboards/uid/YOUR_DASHBOARD_UID > backup.json
```

---

## 📚 相关资源

- [Prometheus文档](https://prometheus.io/docs/)
- [Grafana文档](https://grafana.com/docs/)
- [Alertmanager文档](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [PromQL教程](https://prometheus.io/docs/prometheus/latest/querying/basics/)

---

## ✅ 部署检查清单

部署后验证：

- [ ] Prometheus能够抓取RAG API指标
- [ ] Grafana仪表盘正常显示
- [ ] 告警规则已加载
- [ ] Alertmanager能够发送测试告警
- [ ] 所有服务持久化卷已挂载
- [ ] 修改了默认密码
- [ ] 配置了生产环境告警通道（Slack/PagerDuty/Email）
- [ ] 设置了定期备份任务
- [ ] 团队成员已培训

---

**部署完成！** 🎉

访问 http://localhost:3000 查看监控仪表盘。
