"""
Material model - stores material images
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from . import Base


class Material(Base):
    """
    Material model - represents a material image
    """
    __tablename__ = 'materials'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey('projects.id'), nullable=True)  # Can be null, for global materials not belonging to a project
    filename = Column(String(500), nullable=False)
    relative_path = Column(String(500), nullable=False)  # Path relative to the upload_folder
    url = Column(String(500), nullable=False)  # URL accessible by the frontend
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # Note: SQLAlchemy doesn't support onupdate in declarative base directly
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'filename': self.filename,
            'url': self.url,
            'relative_path': self.relative_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    # Relationships
    project = relationship('Project', back_populates='materials')
    
    def __repr__(self):
        return f'<Material {self.id}: {self.filename} (project={self.project_id or "None"})>'