"""
Debug endpoint to test authentication directly in the running server
Add this temporarily to app/api/main.py
"""

# Add this route to your FastAPI app for debugging
from fastapi import APIRouter
from app.api.utils.auth_dependencies import auth_service

debug_router = APIRouter()

@debug_router.get("/debug/test-auth")
def debug_test_auth():
    """Debug endpoint to test authentication"""
    try:
        # Test with admin
        user1 = auth_service.user_manager.authenticate('admin', 'Admin123456!')

        # Test with testadmin
        user2 = auth_service.user_manager.authenticate('testadmin', 'TestAdmin123!')

        # Get DB path
        db_path = str(auth_service.db_path)

        return {
            "db_path": db_path,
            "admin_auth": "SUCCESS" if user1 else "FAILED",
            "admin_user": user1,
            "testadmin_auth": "SUCCESS" if user2 else "FAILED",
            "testadmin_user": user2,
        }
    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__
        }

# Include this router in your app
# app.include_router(debug_router)
