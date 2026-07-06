"""Debug authentication issue"""
from app.api.utils.auth_dependencies import auth_service
from app.services.auth.validation import validate_username

# Test 1: Direct authentication
print("="*60)
print("Test 1: Direct Authentication")
print("="*60)
username = "admin"
password = "Admin123456!"

try:
    validated_username = validate_username(username)
    print(f"Validated username: {validated_username}")

    user = auth_service.user_manager.authenticate(username, password)
    print(f"Auth result: {user}")

    if user:
        print("\n✅ Authentication SUCCESSFUL")
        print(f"   User ID: {user['user_id']}")
        print(f"   Username: {user['username']}")
        print(f"   Role: {user['role']}")
        print(f"   Status: {user['status']}")
    else:
        print("\n❌ Authentication FAILED - returned None")

except Exception as e:
    print(f"\n❌ Authentication ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Full login flow
print("\n" + "="*60)
print("Test 2: Full Login Flow (auth_service.login)")
print("="*60)

try:
    session_data = auth_service.login(username, password)
    print("✅ Login SUCCESSFUL")
    print(f"   Token: {session_data['token'][:20]}...")
    print(f"   User: {session_data['user']}")
except ValueError as e:
    print(f"❌ Login FAILED: {e}")
except Exception as e:
    print(f"❌ Login ERROR: {e}")
    import traceback
    traceback.print_exc()
