import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# We will expect the user to provide this in their .env file later when it's time to connect.
# For now this just sets up the basic machinery without breaking anything.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/webenoid")

# Create the async database engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

# Create a highly concurrent session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Dependency to inject into FastAPI routes when needed
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
