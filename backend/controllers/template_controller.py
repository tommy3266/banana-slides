"""
Template Controller - handles template-related endpoints
"""
import logging
from fastapi import APIRouter, Request, UploadFile, File
from models import db, Project, UserTemplate
from utils import success_response, error_response, not_found, bad_request, allowed_file
from services import FileService
from datetime import datetime
import os

logger = logging.getLogger(__name__)

template_router = APIRouter()
user_template_router = APIRouter(prefix='/api/user-templates')


@template_router.post('/{project_id}/template')
async def upload_template(project_id: str, file: UploadFile = File(...)):
    """
    Upload template image
    
    Content-Type: multipart/form-data
    Form: template_image=@file.png
    """
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        
        if not project:
            return not_found('Project')
        
        # Validate file extension
        if not allowed_file(file.filename, set(['png', 'jpg', 'jpeg', 'gif', 'webp'])):
            return bad_request("Invalid file type. Allowed types: png, jpg, jpeg, gif, webp")
        
        # Save template
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        file_path = await file_service.save_template_image_fastapi(file, project_id)  # Added await
        
        # Update project
        project.template_image_path = file_path
        project.updated_at = datetime.utcnow()
        
        db.commit()
        
        return success_response({
            'template_image_url': f'/files/{project_id}/template/{file_path.split("/")[-1]}'
        })
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@template_router.delete('/{project_id}/template')
async def delete_template(project_id: str):
    """
    Delete template
    """
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        
        if not project:
            return not_found('Project')
        
        if not project.template_image_path:
            return bad_request("No template to delete")
        
        # Delete template file
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        file_service.delete_template(project_id)
        
        # Update project
        project.template_image_path = None
        project.updated_at = datetime.utcnow()
        
        db.commit()
        
        return success_response(message="Template deleted successfully")
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@template_router.get('/templates')
async def get_system_templates():
    """
    Get system preset templates
    
    Note: This is a placeholder for future implementation
    """
    # TODO: Implement system templates
    templates = []
    
    return success_response({
        'templates': templates
    })


# ========== User Template Endpoints ==========

@user_template_router.post('')
async def upload_user_template(file: UploadFile = File(...), name: str = None):
    """
    Upload user template image
    
    Content-Type: multipart/form-data
    Form: template_image=@file.png
    Optional: name=Template Name
    """
    try:
        # Validate file extension
        if not allowed_file(file.filename, set(['png', 'jpg', 'jpeg', 'gif', 'webp'])):
            return bad_request("Invalid file type. Allowed types: png, jpg, jpeg, gif, webp")
        
        # Get file size
        file_content = await file.read()
        file_size = len(file_content)
        
        # Generate template ID first
        import uuid
        template_id = str(uuid.uuid4())
        
        # Reset file pointer to beginning
        await file.seek(0)
        
        # Save template file first (using the generated ID)
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        file_path = await file_service.save_user_template_fastapi(file, template_id)  # Added await
        
        # Create template record with file_path already set
        template = UserTemplate(
            id=template_id,
            name=name,
            file_path=file_path,
            file_size=file_size
        )
        db.add(template)
        db.commit()
        
        return success_response(template.to_dict())
    
    except Exception as e:
        import traceback
        db.rollback()
        error_msg = str(e)
        logger.error(f"Error uploading user template: {error_msg}", exc_info=True)
        # 在开发环境中返回详细错误，生产环境返回通用错误
        # Note: We don't have access to app config in FastAPI, so we always return detailed error in development
        return error_response('SERVER_ERROR', error_msg, 500)


@user_template_router.get('/list')
async def list_user_templates():
    """
    Get list of user templates
    """
    try:
        templates = db.query(UserTemplate).order_by(UserTemplate.created_at.desc()).all()
        
        return success_response({
            'templates': [template.to_dict() for template in templates]
        })
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@user_template_router.delete('/{template_id}')
async def delete_user_template(template_id: str):
    """
    Delete user template
    """
    try:
        template = db.query(UserTemplate).filter(UserTemplate.id == template_id).first()
        
        if not template:
            return not_found('UserTemplate')
        
        # Delete template file
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        file_service.delete_user_template(template_id)
        
        # Delete template record
        db.delete(template)
        db.commit()
        
        return success_response(message="Template deleted successfully")
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)