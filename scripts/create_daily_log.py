#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建日常工作日志的脚本

使用方法:
    python scripts/create_daily_log.py                # 创建今天的日志
    python scripts/create_daily_log.py --date 2026-08-18  # 创建指定日期的日志
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import argparse

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def get_project_root() -> Path:
    """获取项目根目录"""
    current = Path(__file__).resolve().parent
    return current.parent


def create_daily_log(date_str: str = None, force: bool = False):
    """创建日常工作日志文件夹和模板文件"""

    # 获取日期
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            print(f"❌ 日期格式错误，请使用 YYYY-MM-DD 格式")
            sys.exit(1)
    else:
        date_obj = datetime.now()

    date_str = date_obj.strftime("%Y-%m-%d")

    # 创建日志目录
    project_root = get_project_root()
    log_dir = project_root / "docs" / "development" / "daily-logs" / date_str

    if log_dir.exists() and not force:
        # 检查是否有文件
        existing_files = list(log_dir.glob("*.md"))
        if existing_files:
            print(f"⚠️  日志目录已存在且包含文件: {log_dir}")
            print(f"   已有文件: {', '.join([f.name for f in existing_files])}")
            print(f"   使用 --force 参数强制覆盖")
            sys.exit(1)

    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 创建日志目录: {log_dir}")

    # 创建四个模板文件
    files = {
        "plan.md": f"""# 工作计划 - {date_str}

**日期**: {date_str}
**记录人**: [你的名字]
**状态**: 进行中

## 今日目标

### 主要任务
- [ ] 任务1：[描述]
- [ ] 任务2：[描述]
- [ ] 任务3：[描述]

### 次要任务
- [ ] 任务4：[描述]
- [ ] 任务5：[描述]

## 任务详情

### 任务1：[标题]
**优先级**: 高 / 中 / 低
**预计时间**: X小时
**依赖**: 无

**描述**:
[详细描述任务内容]

**验收标准**:
- [ ] 标准1
- [ ] 标准2

---

## 相关资源

- [相关文档链接]
- [相关代码文件]

## 备注

[任何需要注意的事项]
""",

        "implementation.md": f"""# 实现记录 - {date_str}

**日期**: {date_str}
**记录人**: [你的名字]

## 实现概览

本文档记录今日的代码修改、配置变更和实现细节。

---

## 任务1：[标题]

### 修改的文件
- `path/to/file1.py` - [修改说明]
- `path/to/file2.ts` - [修改说明]

### 关键代码

```python
# 示例代码片段
def example_function():
    pass
```

### 遇到的问题

**问题1**: [描述问题]
- **原因**: [分析]
- **解决方案**: [如何解决]

---

## 测试结果

```bash
# 测试命令
pytest tests/test_example.py -v
```

---

## 待办事项

- [ ] 需要后续跟进的事项1
- [ ] 需要后续跟进的事项2
""",

        "decisions.md": f"""# 技术决策 - {date_str}

**日期**: {date_str}
**记录人**: [你的名字]
**状态**: 已确认

---

## 决策1：[决策标题]

### 背景
[描述为什么需要做这个决策]

### 考虑的方案

#### 方案A：[方案名称]
**优点**:
- 优点1
- 优点2

**缺点**:
- 缺点1

---

#### 方案B：[方案名称]
**优点**:
- 优点1

**缺点**:
- 缺点1
- 缺点2

---

### 最终决策

**选择方案**: A
**决策理由**:
[详细说明为什么选择这个方案]

### 实施计划
1. 步骤1
2. 步骤2

### 影响范围
- **影响的模块**: [列出受影响的模块]
- **需要修改的文件**: [列出主要文件]

---

## 参考资料

- [相关文档链接]
""",

        "summary.md": f"""# 完成总结 - {date_str}

**日期**: {date_str}
**记录人**: [你的名字]
**工作时间**: [开始时间] - [结束时间]

---

## 完成情况概览

| 类别 | 计划任务数 | 完成任务数 | 完成率 |
|------|-----------|-----------|--------|
| 主要任务 | 0 | 0 | 0% |
| 次要任务 | 0 | 0 | 0% |
| **总计** | **0** | **0** | **0%** |

---

## 已完成任务

### ✅ 任务1：[标题]
- **完成时间**: HH:MM
- **实际耗时**: X小时（预计：Y小时）
- **成果**: [描述完成的成果]
- **相关提交**: `commit-hash`

---

## 未完成任务

### ⏸️ 任务2：[标题]
- **进度**: 0%
- **原因**: [说明为什么没完成]
- **计划**: 明天继续

---

## 关键成果

### 代码修改
- **新增代码**: ~XXX 行
- **修改代码**: ~XXX 行
- **新增测试**: XX 个

---

## 遇到的挑战

### 挑战1：[描述]
- **影响**: [说明影响]
- **解决方案**: [如何解决]
- **经验**: [获得的经验]

---

## 经验教训

### 做得好的地方 👍
- 经验1

### 需要改进的地方 💡
- 改进点1

---

## 明日计划

1. [ ] [计划任务1]
2. [ ] [计划任务2]

---

## 相关文档

- [今日计划](plan.md)
- [实现记录](implementation.md)
- [技术决策](decisions.md)
"""
    }

    # 写入文件
    for filename, content in files.items():
        file_path = log_dir / filename
        file_path.write_text(content, encoding='utf-8')
        print(f"✅ 创建文件: {filename}")

    print(f"\n🎉 日志创建完成！")
    print(f"📁 位置: {log_dir}")
    print(f"\n📝 下一步:")
    print(f"   1. 打开 plan.md 填写今日计划")
    print(f"   2. 工作中更新 implementation.md 和 decisions.md")
    print(f"   3. 晚上完成 summary.md 总结")


def main():
    parser = argparse.ArgumentParser(
        description='创建日常工作日志',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--date',
        help='日期（格式：YYYY-MM-DD），默认为今天',
        default=None
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制覆盖已存在的文件'
    )

    args = parser.parse_args()
    create_daily_log(args.date, args.force)


if __name__ == "__main__":
    main()
