"""Test login functionality"""
import sqlite3
from app.services.auth.password_utils import verify_password
from app.services.auth.auth_service import AuthDBService

# Check database
conn = sqlite3.connect('data/app.db')
conn.row_factory = sqlite3.Row
row = conn.execute('SELECT username, salt, password_hash FROM users WHERE username=?', ('admin',)).fetchone()

if row:
    print(f"Username: {row['username']}")
    print(f"Salt (first 20): {row['salt'][:20]}...")
    print(f"Hash (first 20): {row['password_hash'][:20]}...")

    # Test password verification
    test_password = 'Admin123456!'
    is_valid = verify_password(test_password, row['salt'], row['password_hash'])
    print(f"\nPassword '{test_password}' verification: {is_valid}")
else:
    print("Admin user not found!")

conn.close()

# Test through auth service
print("\n" + "="*50)
print("Testing through AuthDBService:")
print("="*50)

db = AuthDBService()
try:
    user = db.user_manager.authenticate('admin', 'Admin123456!')
    print(f"Authentication result: {user}")
except Exception as e:
    print(f"Authentication error: {e}")
