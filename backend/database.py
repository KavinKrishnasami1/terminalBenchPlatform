"""Database models and connection"""
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = "sqlite:///./tbench.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    runs = relationship("Run", back_populates="task", cascade="all, delete-orphan")

class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    model = Column(String, nullable=False)
    status = Column(String, default="queued")  # queued, running, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="runs")
    attempts = relationship("Attempt", back_populates="run", cascade="all, delete-orphan")

class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    status = Column(String, default="queued")  # queued, running, completed, failed
    reward = Column(Float, nullable=True)
    episode_count = Column(Integer, nullable=True)
    output_path = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    run = relationship("Run", back_populates="attempts")
    episodes = relationship("Episode", back_populates="attempt", cascade="all, delete-orphan")
    test_results = relationship("TestResult", back_populates="attempt", cascade="all, delete-orphan")

class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id"), nullable=False)
    episode_number = Column(Integer, nullable=False)
    analysis = Column(Text, nullable=True)
    plan = Column(Text, nullable=True)
    commands = Column(Text, nullable=True)  # JSON string
    task_complete = Column(Boolean, nullable=True)

    attempt = relationship("Attempt", back_populates="episodes")

class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id"), nullable=False)
    test_name = Column(String, nullable=False)
    status = Column(String, nullable=False)  # passed, failed, skipped
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    attempt = relationship("Attempt", back_populates="test_results")

def init_db():
    """Initialize database"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
