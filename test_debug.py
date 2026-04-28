import sys
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from app.api.main import app
from app.api.dependencies import auth_service

client = TestClient(app)

# 创建管理员
admin = auth_service.register("testadmin", "Admin123!@#456")
auth_service.update_user_role(admin["user_id"], "admin")

# 登录
login_resp = client.post("/auth/login", json={
    "username": "testadmin",
    "password": "Admin123!@#456"
})
print(f"Login status: {login_resp.status_code}")
cookie_token = login_resp.cookies.get("auth_token")
print(f"Cookie token: {cookie_token}")

# 直接验证 token
user = auth_service.get_user_by_token(cookie_token)
print(f"User from token: {user}")

# 禁用管理员
auth_service.update_user_status(admin["user_id"], "disabled")

# 再次验证 token
user_after = auth_service.get_user_by_token(cookie_token)
print(f"User after disable: {user_after}")

# 尝试访问
response = client.get("/admin/users")
print(f"Response status: {response.status_code}")
print(f"Response body: {response.json()}")
