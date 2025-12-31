"""Database models package"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from config import Config

# For FastAPI compatibility, we create a SQLAlchemy setup that works with FastAPI
# We'll use SQLAlchemy Core/ORM directly rather than Flask-SQLAlchemy

# Create the base class for declarative models
Base = declarative_base()

# Database engine and session setup for FastAPI
engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    **Config.SQLALCHEMY_ENGINE_OPTIONS,
    # Add specific options for FastAPI compatibility
    echo=False,  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# For thread-local sessions in FastAPI
db_session = scoped_session(SessionLocal)

# Alias db to the session for backward compatibility
db = db_session

# Import all models after Base is defined to avoid circular imports
from .project import Project
from .page import Page
from .task import Task
from .user_template import UserTemplate
from .page_image_version import PageImageVersion
from .material import Material
from .reference_file import ReferenceFile
from .settings import Settings

__all__ = ['db', 'Base', 'engine', 'SessionLocal', 'Project', 'Page', 'Task', 'UserTemplate', 'PageImageVersion', 'Material', 'ReferenceFile', 'Settings']