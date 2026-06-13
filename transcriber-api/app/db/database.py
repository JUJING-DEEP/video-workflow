"""
SQLite database layer using SQLAlchemy
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

from sqlalchemy import Column, DateTime, Enum, String, Text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# Database URL - supports both sqlite and postgres
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./transcriber.db")

# Async engine for aiosqlite
if DATABASE_URL.startswith("sqlite"):
    if "+aiosqlite" not in DATABASE_URL:
        async_database_url = DATABASE_URL.replace("sqlite", "sqlite+aiosqlite")
    else:
        async_database_url = DATABASE_URL
    engine = create_async_engine(async_database_url, echo=False)
else:
    # For postgres, use the same URL
    engine = create_async_engine(DATABASE_URL, echo=False)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class JobModel(Base):
    """SQLAlchemy model for jobs table"""

    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True)
    source_type = Column(String(16), nullable=False)
    source_url = Column(Text, nullable=True)
    file_path = Column(Text, nullable=True)
    language = Column(String(8), default="zh")
    output_style = Column(String(32), default="distilled_original")
    status = Column(String(32), default="pending")
    raw_transcript = Column(Text, nullable=True)
    cleaned_transcript = Column(Text, nullable=True)
    distilled_content = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Database:
    """Database operations"""

    def __init__(self):
        self.engine = engine
        self.session_maker = async_session_maker

    async def init_db(self):
        """Initialize database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session"""
        async with self.session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def create_job(self, job_data: dict) -> JobModel:
        """Create a new job"""
        async with self.session() as session:
            job = JobModel(**job_data)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

    async def get_job(self, job_id: str) -> Optional[JobModel]:
        """Get job by ID"""
        async with self.session() as session:
            from sqlalchemy import select

            result = await session.execute(select(JobModel).where(JobModel.id == job_id))
            return result.scalar_one_or_none()

    async def update_job(self, job_id: str, **updates) -> Optional[JobModel]:
        """Update job fields"""
        async with self.session() as session:
            from sqlalchemy import select, update

            # Get current job
            result = await session.execute(select(JobModel).where(JobModel.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                return None

            # Apply updates
            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(job)
            return job

    async def list_jobs(self, limit: int = 100) -> list[JobModel]:
        """List recent jobs"""
        async with self.session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(JobModel).order_by(JobModel.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get database instance"""
    global _db
    if _db is None:
        _db = Database()
    return _db


async def init_db():
    """Initialize database on startup"""
    db = get_db()
    await db.init_db()