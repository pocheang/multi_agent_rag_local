"""Debug test to check actual response"""
from fastapi.testclient import TestClient
from app.api.main import app
from app.api.dependencies import auth_service
import uuid

# Create admin user
username = f'test_admin_{uuid.uuid4().hex[:8]}'
user = auth_service.create_user_with_role(username, 'AdminPass123!', 'admin')
print(f'Created user: {user["user_id"]}')

# Login
result = auth_service.login(username, 'AdminPass123!')
token = result['token']
print(f'Got token: {token[:20]}...')

# Try to modify own role
client = TestClient(app)
response = client.patch(
    f'/admin/users/{user["user_id"]}/role',
    json={'role': 'super_admin'},
    headers={'Authorization': f'Bearer {token}'}
)
print(f'Status: {response.status_code}')
print(f'Response: {response.json()}')
print(f'Expected: 403 with "cannot modify your own" message')
