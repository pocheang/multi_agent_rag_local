# Backward compatibility shim
# This file maintains the original import path for existing code
# New code should import from app.services.auth instead

from app.services.auth.auth_service import AuthDBService

__all__ = ["AuthDBService"]
