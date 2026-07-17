#!/usr/bin/env python3
"""
Google OAuth 配置检查脚本
检查 OAuth 配置是否正确，并提供配置建议
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from app.core.config import Settings
    from dotenv import load_dotenv

    # 加载环境变量
    env_file = Path(os.getenv("RUNTIME_ENV_FILE", project_root / ".runtime" / "development.env"))
    load_dotenv(env_file)

    # 创建 settings 实例
    settings = Settings()

    print("=" * 60)
    print("Google OAuth 配置检查")
    print("=" * 60)
    print()

    # 检查配置
    has_client_id = bool(settings.google_client_id)
    has_client_secret = bool(settings.google_client_secret)
    redirect_uri = settings.google_redirect_uri

    print("📋 配置状态:")
    print(f"  ✓ Google Client ID: {'已配置' if has_client_id else '❌ 未配置'}")
    if has_client_id:
        print(f"    值: {settings.google_client_id[:20]}...{settings.google_client_id[-10:]}")

    print(f"  ✓ Google Client Secret: {'已配置' if has_client_secret else '❌ 未配置'}")
    if has_client_secret:
        print(f"    值: {settings.google_client_secret[:10]}...***")

    print(f"  ✓ Redirect URI: {redirect_uri}")
    print()

    # 判断是否完全配置
    if has_client_id and has_client_secret:
        print("✅ Google OAuth 已完全配置！")
        print()
        print("🚀 测试步骤:")
        print("  1. 确保后端服务运行在: http://localhost:8000")
        print("  2. 确保前端服务运行在: http://localhost:5173")
        print("  3. 访问: http://localhost:5173/app/login")
        print("  4. 点击 'Google 登录' 按钮")
        print("  5. 使用测试账号授权")
        print()
    else:
        print("⚠️  Google OAuth 未完全配置")
        print()
        print("📝 配置步骤:")
        print("  1. 阅读配置指南: GOOGLE_OAUTH_SETUP.md")
        print("  2. 访问 Google Cloud Console 创建 OAuth 客户端")
        print("  3. 在 .runtime/development.env 中添加:")
        print()
        print("     GOOGLE_CLIENT_ID=你的客户端ID")
        print("     GOOGLE_CLIENT_SECRET=你的客户端密钥")
        print(f"     OAUTH_REDIRECT_URI={redirect_uri}")
        print()
        print("  4. 重启后端服务")
        print()

    # 检查环境变量文件
    if not env_file.exists():
        print("⚠️  未找到运行时配置文件")
        print("  请先运行 deploy/scripts/config.py render 生成 .runtime/development.env")
        print()

    print("=" * 60)
    print()

    # 返回状态码
    sys.exit(0 if (has_client_id and has_client_secret) else 1)

except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保在 rag-local conda 环境中运行此脚本")
    sys.exit(1)
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
