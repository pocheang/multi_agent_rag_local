#!/bin/bash
# P0 缓存安全修复验证脚本

echo "=================================="
echo "P0 缓存安全修复验证"
echo "=================================="
echo ""

# 检查 conda 环境
if [ "$CONDA_DEFAULT_ENV" != "rag-local" ]; then
    echo "⚠️  警告: 未激活 rag-local 环境"
    echo "请运行: conda activate rag-local"
    exit 1
fi

echo "✓ Conda 环境已激活: $CONDA_DEFAULT_ENV"
echo ""

# 运行 P0 安全测试
echo "运行 P0 安全测试..."
echo "=================================="
pytest tests/security/test_p0_cache_fixes.py -v --tb=short

if [ $? -eq 0 ]; then
    echo ""
    echo "=================================="
    echo "✅ P0 安全测试全部通过！"
    echo "=================================="
    echo ""

    # 显示测试覆盖率
    echo "生成测试覆盖率报告..."
    pytest tests/security/test_p0_cache_fixes.py --cov=app.services.runtime.query_result_cache --cov-report=term-missing

    echo ""
    echo "=================================="
    echo "下一步操作："
    echo "1. 审查代码变更"
    echo "2. 运行完整测试套件: pytest tests/ -v"
    echo "3. 执行性能测试"
    echo "4. 部署到开发环境"
    echo "=================================="
else
    echo ""
    echo "=================================="
    echo "❌ 测试失败，请检查错误信息"
    echo "=================================="
    exit 1
fi
