import os
import httpx
from datetime import datetime, timedelta
import jwt
from typing import Optional

# Retrieve secrets from environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_webenoid_key_change_in_production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 30  # Long-lived token for extension


async def verify_google_token(token: str) -> Optional[dict]:
    """
    Verifies a Google OAuth2 **Access Token** (returned by chrome.identity.getAuthToken)
    by calling Google's tokeninfo/userinfo endpoint.
    """
    try:
        async with httpx.AsyncClient() as client:
            # Use the userinfo endpoint to validate the access token and get user info
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=8.0
            )

        if resp.status_code != 200:
            print(f"[AUTH ERROR] Google userinfo failed: {resp.status_code} {resp.text}")
            return None

        info = resp.json()
        return {
            "google_id": info.get("sub"),
            "email": info.get("email", ""),
            "name": info.get("name", ""),
        }
    except Exception as e:
        print(f"[AUTH ERROR] Google Token Verification failed: {e}")
        return None


def create_access_token(user_id: str) -> str:
    """
    Creates a WebEnoid JWT containing the user's database UUID.
    """
    expire = datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS)
    to_encode = {"sub": user_id, "exp": expire}
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str) -> Optional[str]:
    """
    Verifies a WebEnoid JWT and returns the user's UUID string if valid.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except jwt.ExpiredSignatureError:
        print("[AUTH ERROR] JWT Expired")
        return None
    except jwt.PyJWTError:
        print("[AUTH ERROR] JWT Invalid")
        return None
