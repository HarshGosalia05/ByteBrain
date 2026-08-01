from fastapi import HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import json
import base64

security_scheme = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> dict:
    """
    Extracts the user identity from the token provided by Next.js.
    Since Next.js currently uses a plaintext JSON cookie for session (which is a known 
    temporary measure per analysis_results.md), the Next.js BFF will pass that JSON string 
    (possibly base64 encoded) as the Bearer token for integration testing until JWT is implemented.
    """
    token = credentials.credentials
    try:
        # Check if the token is base64 encoded JSON
        try:
            decoded_bytes = base64.b64decode(token)
            token = decoded_bytes.decode('utf-8')
        except Exception:
            pass # Use as-is if not base64
        
        user_data = json.loads(token)
        if not user_data or "role" not in user_data:
            raise ValueError("Invalid user payload")
            
        return user_data
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
