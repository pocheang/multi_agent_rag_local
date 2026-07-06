"""Create a test admin user"""
from app.services.auth.auth_service import AuthDBService

db = AuthDBService()

try:
    user = db.create_user_with_role('testadmin', 'TestAdmin123!', 'admin')
    print(f'Created user: {user["username"]} (role: {user["role"]})')

    # Test authentication immediately
    auth_result = db.user_manager.authenticate('testadmin', 'TestAdmin123!')
    print(f'Auth test: {"SUCCESS" if auth_result else "FAILED"}')

except ValueError as e:
    print(f'User might already exist: {e}')
    # Try to authenticate existing user
    auth_result = db.user_manager.authenticate('testadmin', 'TestAdmin123!')
    print(f'Existing user auth: {"SUCCESS" if auth_result else "FAILED"}')
except Exception as e:
    print(f'Error: {e}')
