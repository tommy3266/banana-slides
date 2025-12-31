"""
Page model
"""
import uuid
import json
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from . import Base


class Page(Base):
    """
    Page model - represents a single PPT page/slide
    """
    __tablename__ = 'pages'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey('projects.id'), nullable=False)
    order_index = Column(Integer, nullable=False)
    part = Column(String(200), nullable=True)  # Optional section name
    outline_content = Column(Text, nullable=True)  # JSON string
    description_content = Column(Text, nullable=True)  # JSON string
    generated_image_path = Column(String(500), nullable=True)
    status = Column(String(50), nullable=False, default='DRAFT')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)  # Note: SQLAlchemy doesn't support onupdate in declarative base directly
    
    # Relationships
    project = relationship('Project', back_populates='pages')
    image_versions = relationship('PageImageVersion', back_populates='page', 
                                     lazy='dynamic', cascade='all, delete-orphan',
                                     order_by='PageImageVersion.version_number.desc()')
    
    def get_outline_content(self):
        """Parse outline_content from JSON string"""
        if self.outline_content:
            try:
                return json.loads(self.outline_content)
            except json.JSONDecodeError:
                return None
        return None
    
    def set_outline_content(self, data):
        """Set outline_content as JSON string"""
        if data:
            self.outline_content = json.dumps(data, ensure_ascii=False)
        else:
            self.outline_content = None
    
    def get_description_content(self):
        """Parse description_content from JSON string"""
        if self.description_content:
            try:
                return json.loads(self.description_content)
            except json.JSONDecodeError:
                return None
        return None
    
    def set_description_content(self, data):
        """Set description_content as JSON string"""
        if data:
            self.description_content = json.dumps(data, ensure_ascii=False)
        else:
            self.description_content = None
    
    def to_dict(self, include_versions=False):
        """Convert to dictionary"""
        data = {
            'page_id': self.id,
            'order_index': self.order_index,
            'part': self.part,
            'outline_content': self.get_outline_content(),
            'description_content': self.get_description_content(),
            'generated_image_url': f'/files/{self.project_id}/pages/{self.generated_image_path.split("/")[-1]}' if self.generated_image_path else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_versions:
            # For SQLAlchemy Core compatibility, use all() method
            image_versions_list = self.image_versions.all() if hasattr(self.image_versions, 'all') else list(self.image_versions)
            data['image_versions'] = [v.to_dict() for v in image_versions_list]
        
        return data
    
    def __repr__(self):
        return f'<Page {self.id}: {self.order_index} - {self.status}>'