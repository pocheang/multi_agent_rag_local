"""
用户管理脚本 - 重置密码或创建新用户
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.auth_db import AuthDB

def main():
    db = AuthDB()

    print("=" * 50)
    print("用户管理工具")
    print("=" * 50)

    # 列出现有用户
    print("\n现有用户:")
    users = db.list_users()
    if not users:
        print("  (无用户)")
    else:
        for u in users:
            print(f"  - {u.username} (role: {u.role}, status: {u.status})")

    print("\n" + "=" * 50)
    print("选择操作:")
    print("1. 创建新用户")
    print("2. 重置用户密码")
    print("3. 快速创建 admin/admin 账号")
    print("4. 退出")
    print("=" * 50)

    choice = input("\n请选择 (1-4): ").strip()

    if choice == "1":
        username = input("用户名: ").strip()
        password = input("密码: ").strip()
        role = input("角色 (admin/analyst/viewer, 默认 admin): ").strip() or "admin"

        try:
            user = db.create_user(username, password, role)
            print(f"\n✅ 用户创建成功: {user.username} (role: {user.role})")
        except Exception as e:
            print(f"\n❌ 创建失败: {e}")

    elif choice == "2":
        username = input("用户名: ").strip()
        new_password = input("新密码: ").strip()

        try:
            # 获取用户
            user = db.get_user(username)
            if not user:
                print(f"\n❌ 用户 '{username}' 不存在")
                return

            # 更新密码
            db.update_user(user.user_id, password=new_password)
            print(f"\n✅ 密码重置成功: {username}")
        except Exception as e:
            print(f"\n❌ 重置失败: {e}")

    elif choice == "3":
        try:
            # 检查是否已存在
            existing = db.get_user("admin")
            if existing:
                # 重置密码
                db.update_user(existing.user_id, password="admin")
                print("\n✅ admin 账号密码已重置为: admin")
            else:
                # 创建新用户
                user = db.create_user("admin", "admin", "admin")
                print(f"\n✅ 创建成功: admin/admin (role: {user.role})")
        except Exception as e:
            print(f"\n❌ 操作失败: {e}")

    elif choice == "4":
        print("\n再见!")
        return

    else:
        print("\n❌ 无效选择")

if __name__ == "__main__":
    main()
