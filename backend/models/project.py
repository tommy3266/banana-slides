"""
Project model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.orm import relationship
from . import Base


class Project(Base):
    """
    Project model - represents a PPT project
    """
    __tablename__ = 'projects'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    idea_prompt = Column(Text, nullable=True)
    outline_text = Column(Text, nullable=True)  # 用户输入的大纲文本（用于outline类型）
    description_text = Column(Text, nullable=True)  # 用户输入的描述文本（用于description类型）
    extra_requirements = Column(Text, nullable=True)  # 额外要求，应用到每个页面的AI提示词
    creation_type = Column(String(20), nullable=False, default='idea')  # idea|outline|descriptions
    template_image_path = Column(String(500), nullable=True)
    template_style = Column(Text, nullable=True)  # 风格描述文本（无模板模式）
    status = Column(String(50), nullable=False, default='DRAFT')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    pages = relationship('Page', back_populates='project', lazy='dynamic', 
                           cascade='all, delete-orphan', order_by='Page.order_index')
    tasks = relationship('Task', back_populates='project', lazy='dynamic',
                           cascade='all, delete-orphan')
    materials = relationship('Material', back_populates='project', lazy='dynamic',
                           cascade='all, delete-orphan')
    
    def to_dict(self, include_pages=False):
        """Convert to dictionary"""
        # Format created_at and updated_at with UTC timezone indicator for proper frontend parsing
        created_at_str = None
        if self.created_at:
            created_at_str = self.created_at.isoformat() + 'Z' if not self.created_at.tzinfo else self.created_at.isoformat()
        
        updated_at_str = None
        if self.updated_at:
            updated_at_str = self.updated_at.isoformat() + 'Z' if not self.updated_at.tzinfo else self.updated_at.isoformat()
        
        data = {
            'project_id': self.id,
            'idea_prompt': self.idea_prompt,
            'outline_text': self.outline_text,
            'description_text': self.description_text,
            'extra_requirements': self.extra_requirements,
            'creation_type': self.creation_type,
            'template_image_url': f'/files/{self.id}/template/{self.template_image_path.split("/")[-1]}' if self.template_image_path else None,
            'template_style': self.template_style,
            'status': self.status,
            'created_at': created_at_str,
            'updated_at': updated_at_str,
        }
        
        if include_pages:
            data['pages'] = [page.to_dict() for page in self.pages.order_by('order_index')]
        
        return data
    
    def __repr__(self):
        return f'<Project {self.id}: {self.status}>'