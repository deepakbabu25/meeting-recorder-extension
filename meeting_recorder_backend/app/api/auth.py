from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.db.models import User
from app.core.security import verify_google_token, create_access_token

router = APIRouter()

class GoogleTokenRequest(BaseModel):
    token: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    name: str

@router.post("/google", response_model=AuthResponse)
async def google_auth(
    payload: GoogleTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    1. Verifies the raw Google ID Token with Google's public keys.
    2. Upserts user into PostgreSQL 'users' table based on google_id.
    3. Issues a long-lived WebEnoid JWT tying the user to their Postgres UUID.
    """
    user_info = await verify_google_token(payload.token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid Google token.")

    google_id = user_info["google_id"]
    email = user_info["email"]
    name = user_info["name"]

    # Check if user already exists
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        # Create a new user profile
        user = User(google_id=google_id, email=email, name=name)
        db.add(user)
        # Flush to DB to assign a UUID to user.id immediately
        await db.flush() 
        # Commit to save
        await db.commit()
    
    # Generate long-lived extension token using the Database UUID
    access_token = create_access_token(str(user.id))

    return AuthResponse(access_token=access_token, name=user.name)
