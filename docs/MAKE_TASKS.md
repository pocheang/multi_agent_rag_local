# 🛠️ QueryMind 项目工具任务

## 📋 可用的Make任务

### 环境安装
```bash
make install          # 创建虚拟环境并安装依赖
make fe-install       # 安装前端依赖
```

### 服务启动
```bash
make up              # 启动Docker服务（Neo4j）
make api             # 启动后端API服务（8000端口）
make fe-dev          # 启动前端开发服务（5173端口）
```

### 数据处理
```bash
make ingest          # 执行数据摄入
```

### 测试与质量
```bash
make test            # 运行pytest测试
make quality-gate    # 运行质量检查
make benchmark       # 运行性能基准测试
```

### 构建
```bash
make fe-build        # 构建前端生产版本
```

### 运维
```bash
make apply-rollback  # 应用回滚配置
```

### CLI工具
```bash
make cli             # 运行命令行查询工具
```

---

## 🚀 常用任务组合

### 首次安装
```bash
make install
make fe-install
make up
```

### 启动开发环境
```bash
# 终端1
make api

# 终端2
make fe-dev
```

### 完整测试
```bash
make test
make quality-gate
make benchmark
```

---

## 📊 当前服务状态

✅ 前端: http://localhost:5173 (运行中)
✅ 后端: http://localhost:8000 (需要启动)

---

最后更新：2026-07-01
