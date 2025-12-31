"""
Page Image Version model - stores historical versions of generated images
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from . import Base


class PageImageVersion(Base):
    """
    Page Image Version model - represents a historical version of a page's generated image
    """
    __tablename__ = 'page_image_versions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id = Column(String(36), ForeignKey('pages.id'), nullable=False, index=True)
    image_path = Column(String(500), nullable=False)
    version_number = Column(Integer, nullable=False)  # 版本号，从1开始递增
    is_current = Column(Boolean, nullable=False, default=False)  # 是否为当前使用的版本
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    page = relationship('Page', back_populates='image_versions')
    
    def to_dict(self):
        """Convert to dictionary"""
        # Get project_id from page relationship
        project_id = self.page.project_id if self.page else None
        # Format created_at with UTC timezone indicator for proper frontend parsing
        created_at_str = None
        if self.created_at:
            # Add 'Z' suffix to indicate UTC timezone, so frontend can parse it correctly
            created_at_str = self.created_at.isoformat() + 'Z' if not self.created_at.tzinfo else self.created_at.isoformat()
        return {
            'version_id': self.id,
            'page_id': self.page_id,
            'image_path': self.image_path,
            'image_url': f'/files/{project_id}/pages/{self.image_path.split("/")[-1]}' if self.image_path and project_id else None,
            'version_number': self.version_number,
            'is_current': self.is_current,
            'created_at': created_at_str,
        }
    
    def __repr__(self):
        return f'<PageImageVersion {self.id}: page={self.page_id}, version={self.version_number}, current={self.is_current}>'