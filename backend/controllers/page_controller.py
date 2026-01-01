"""
Page Controller - handles page-related endpoints
"""
import logging
from fastapi import APIRouter, Request, UploadFile, File, Form
from models import db, Project, Page, PageImageVersion, Task
from models.request_models import CreatePageRequest, UpdatePageOutlineRequest, UpdatePageDescriptionRequest, GeneratePageDescriptionRequest, GeneratePageImageRequest, EditPageImageRequest
from utils import success_response, error_response, not_found, bad_request
from services import AIService, FileService, ProjectContext
from services.task_manager import task_manager, generate_single_page_image_task, edit_page_image_task
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
import shutil
import tempfile
import json
import os

logger = logging.getLogger(__name__)

page_router = APIRouter()


@page_router.post('/{project_id}/pages')
async def create_page(project_id: str, request_data: CreatePageRequest):
    """
    Add new page
    
    Request body:
    {
        "order_index": 2,
        "part": "optional",
        "outline_content": {"title": "...", "points": [...]}
    }
    """
    try:
        # Use session to query
        project = db.query(Project).filter(Project.id == project_id).first()
        
        if not project:
            return not_found('Project')
        
        if request_data.order_index is None:
            return bad_request("order_index is required")
        
        # Create new page
        page = Page(
            project_id=project_id,
            order_index=request_data.order_index,
            part=request_data.part,
            status='DRAFT'
        )
        
        if request_data.outline_content:
            page.set_outline_content(request_data.outline_content)
        
        db.add(page)
        
        # Update other pages' order_index if necessary
        # Use session to query
        other_pages = db.query(Page).filter(
            Page.project_id == project_id,
            Page.order_index >= request_data.order_index
        ).all()
        
        for p in other_pages:
            if p.id != page.id:
                p.order_index += 1
        
        project.updated_at = datetime.utcnow()
        db.commit()
        
        return success_response(page.to_dict(), status_code=201)
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@page_router.delete('/{project_id}/pages/{page_id}')
async def delete_page(project_id: str, page_id: str):
    """
    Delete page
    """
    try:
        # Use session to query
        page = db.query(Page).filter(Page.id == page_id).first()
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        # Delete page image if exists
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        file_service.delete_page_image(project_id, page_id)
        
        # Delete page
        db.delete(page)
        
        # Update project
        # Use session to query
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.updated_at = datetime.utcnow()
        
        db.commit()
        
        return success_response(message="Page deleted successfully")
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@page_router.put('/{project_id}/pages/{page_id}/outline')
async def update_page_outline(project_id: str, page_id: str, request_data: UpdatePageOutlineRequest):
    """
    Edit page outline
    
    Request body:
    {
        "outline_content": {"title": "...", "points": [...]}
    }
    """
    try:
        # Use session to query
        page = db.query(Page).filter(Page.id == page_id).first()
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        if not request_data.outline_content:
            return bad_request("outline_content is required")
        
        page.set_outline_content(request_data.outline_content)
        page.updated_at = datetime.utcnow()
        
        # Update project
        # Use session to query
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.updated_at = datetime.utcnow()
        
        db.commit()
        
        return success_response(page.to_dict())
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@page_router.put('/{project_id}/pages/{page_id}/description')
async def update_page_description(project_id: str, page_id: str, request_data: UpdatePageDescriptionRequest):
    """
    Edit description
    
    Request body:
    {
        "description_content": {
            "title": "...",
            "text_content": ["...", "..."],
            "layout_suggestion": "..."
        }
    }
    """
    try:
        # Use session to query
        page = db.query(Page).filter(Page.id == page_id).first()
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        if not request_data.description_content:
            return bad_request("description_content is required")
        
        page.set_description_content(request_data.description_content)
        page.updated_at = datetime.utcnow()
        
        # Update project
        # Use session to query
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.updated_at = datetime.utcnow()
        
        db.commit()
        
        return success_response(page.to_dict())
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@page_router.post('/{project_id}/pages/{page_id}/generate/description')
async def generate_page_description(project_id: str, page_id: str, request_data: GeneratePageDescriptionRequest):
    """
    Generate single page description
    
    Request body:
    {
        "force_regenerate": false
    }
    """
    try:
        # Use session to query
        page = db.query(Page).filter(Page.id == page_id).first()
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        # Use session to query
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return not_found('Project')
        
        force_regenerate = request_data.force_regenerate
        language = request_data.language or os.getenv('OUTPUT_LANGUAGE', 'zh')
        
        # Check if already generated
        if page.get_description_content() and not force_regenerate:
            return bad_request("Description already exists. Set force_regenerate=true to regenerate")
        
        # Get outline content
        outline_content = page.get_outline_content()
        if not outline_content:
            return bad_request("Page must have outline content first")
        
        # Reconstruct full outline
        # Use session to query
        all_pages = db.query(Page).filter(Page.project_id == project_id).order_by(Page.order_index).all()
        outline = []
        for p in all_pages:
            oc = p.get_outline_content()
            if oc:
                page_data = oc.copy()
                if p.part:
                    page_data['part'] = p.part
                outline.append(page_data)
        
        # Initialize AI service
        ai_service = AIService()
        
        # Get reference files content and create project context
        from controllers.project_controller import _get_project_reference_files_content
        reference_files_content = _get_project_reference_files_content(project_id)
        project_context = ProjectContext(project, reference_files_content)
        
        # Generate description
        page_data = outline_content.copy()
        if page.part:
            page_data['part'] = page.part
        
        desc_text = ai_service.generate_page_description(
            project_context,
            outline,
            page_data,
            page.order_index + 1,
            language=language
        )
        
        # Save description
        desc_content = {
            "text": desc_text,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        page.set_description_content(desc_content)
        page.status = 'DESCRIPTION_GENERATED'
        page.updated_at = datetime.utcnow()
        
        db.commit()
        
        return success_response(page.to_dict())
    
    except Exception as e:
        db.rollback()
        return error_response('AI_SERVICE_ERROR', str(e), 503)


@page_router.post('/{project_id}/pages/{page_id}/generate/image')
async def generate_page_image(project_id: str, page_id: str, request_data: GeneratePageImageRequest):
    """
    Generate single page image
    
    Request body:
    {
        "use_template": true,
        "force_regenerate": false
    }
    """
    try:
        # Use session to query
        page = db.query(Page).filter(Page.id == page_id).first()
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        # Use session to query
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return not_found('Project')
        
        use_template = request_data.use_template
        force_regenerate = request_data.force_regenerate
        language = request_data.language or os.getenv('OUTPUT_LANGUAGE', 'zh')
        
        # Check if already generated
        if page.generated_image_path and not force_regenerate:
            return bad_request("Image already exists. Set force_regenerate=true to regenerate")
        
        # Get description content
        desc_content = page.get_description_content()
        if not desc_content:
            return bad_request("Page must have description content first")
        
        # Reconstruct full outline with part structure
        # Use session to query
        all_pages = db.query(Page).filter(Page.project_id == project_id).order_by(Page.order_index).all()
        outline = []
        current_part = None
        current_part_pages = []
        
        for p in all_pages:
            oc = p.get_outline_content()
            if not oc:
                continue
                
            page_data = oc.copy()
            
            # 如果当前页面属于一个 part
            if p.part:
                # 如果这是新的 part，先保存之前的 part（如果有）
                if current_part and current_part != p.part:
                    outline.append({
                        "part": current_part,
                        "pages": current_part_pages
                    })
                    current_part_pages = []
                
                current_part = p.part
                # 移除 part 字段，因为它在顶层
                if 'part' in page_data:
                    del page_data['part']
                current_part_pages.append(page_data)
            else:
                # 如果当前页面不属于任何 part，先保存之前的 part（如果有）
                if current_part:
                    outline.append({
                        "part": current_part,
                        "pages": current_part_pages
                    })
                    current_part = None
                    current_part_pages = []
                
                # 直接添加页面
                outline.append(page_data)
        
        # 保存最后一个 part（如果有）
        if current_part:
            outline.append({
                "part": current_part,
                "pages": current_part_pages
            })
        
        # Initialize services
        ai_service = AIService()
        
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        
        # Get template path
        ref_image_path = None
        if use_template:
            ref_image_path = file_service.get_template_path(project_id)
        
        # 检查是否有模板图片或风格描述
        # 如果都没有，则返回错误
        if not ref_image_path and not project.template_style:
            return bad_request("No template image or style description found for project")
        
        # Generate prompt
        page_data = page.get_outline_content() or {}
        if page.part:
            page_data['part'] = page.part
        
        # 获取描述文本（可能是 text 字段或 text_content 数组）
        desc_text = desc_content.get('text', '')
        if not desc_text and desc_content.get('text_content'):
            # 如果 text 字段不存在，尝试从 text_content 数组获取
            text_content = desc_content.get('text_content', [])
            if isinstance(text_content, list):
                desc_text = '\n'.join(text_content)
            else:
                desc_text = str(text_content)
        
        # 从当前页面的描述内容中提取图片 URL（在生成 prompt 之前提取，以便告知 AI）
        additional_ref_images = []
        has_material_images = False
        
        # 从描述文本中提取图片
        if desc_text:
            image_urls = ai_service.extract_image_urls_from_markdown(desc_text)
            if image_urls:
                logger.info(f"Found {len(image_urls)} image(s) in page {page_id} description")
                additional_ref_images = image_urls
                has_material_images = True
        
        # 合并额外要求和风格描述
        combined_requirements = project.extra_requirements or ""
        if project.template_style:
            style_requirement = f"\n\nppt页面风格描述：\n\n{project.template_style}"
            combined_requirements = combined_requirements + style_requirement
        
        # Create async task for image generation
        task = Task(
            project_id=project_id,
            task_type='GENERATE_PAGE_IMAGE',
            status='PENDING'
        )
        task.set_progress({
            'total': 1,
            'completed': 0,
            'failed': 0
        })
        db.add(task)
        db.commit()
        
        # Submit background task
        from main import app  # Import the app instance
        task_manager.submit_task(
            task.id,
            generate_single_page_image_task,
            project_id,
            page_id,
            ai_service,
            file_service,
            outline,
            use_template,
            os.getenv('DEFAULT_ASPECT_RATIO', '16:9'),
            os.getenv('DEFAULT_RESOLUTION', '2K'),
            app,
            combined_requirements if combined_requirements.strip() else None,
            language
        )
        
        # Return task_id immediately
        return success_response({
            'task_id': task.id,
            'page_id': page_id,
            'status': 'PENDING'
        }, status_code=202)
    
    except Exception as e:
        db.rollback()
        return error_response('AI_SERVICE_ERROR', str(e), 503)


@page_router.post('/{project_id}/pages/{page_id}/edit/image')
async def edit_page_image(project_id: str, page_id: str, request_data: EditPageImageRequest):
    """
    Edit page image
    
    Request body (JSON or multipart/form-data):
    {
        "edit_instruction": "更改文本框样式为虚线",
        "context_images": {
            "use_template": true,  // 是否使用template图片
            "desc_image_urls": ["url1", "url2"],  // desc中的图片URL列表
            "uploaded_image_ids": ["file1", "file2"]  // 上传的图片文件ID列表（在multipart中）
        }
    }
    
    For multipart/form-data:
    - edit_instruction: text field
    - use_template: text field (true/false)
    - desc_image_urls: JSON array string
    - context_images: file uploads (multiple files with key "context_images")
    """
    try:
        # Use session to query
        page = db.query(Page).filter(Page.id == page_id).first()
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        if not page.generated_image_path:
            return bad_request("Page must have generated image first")
        
        # Use session to query
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return not_found('Project')
        
        if not request_data.edit_instruction:
            return bad_request("edit_instruction is required")
        
        # Initialize services
        ai_service = AIService()
        
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        
        # Parse request data (support both JSON and multipart/form-data)
        # In FastAPI, we need to handle this differently - let's use a JSON request for now
        
        data = request_data
        
        # Get current image path
        current_image_path = file_service.get_absolute_path(page.generated_image_path)
        
        # Get original description if available
        original_description = None
        desc_content = page.get_description_content()
        if desc_content:
            # Extract text from description_content
            original_description = desc_content.get('text') or ''
            # If text is not available, try to construct from text_content
            if not original_description and desc_content.get('text_content'):
                if isinstance(desc_content['text_content'], list):
                    original_description = '\n'.join(desc_content['text_content'])
                else:
                    original_description = str(desc_content['text_content'])
        
        # Collect additional reference images
        additional_ref_images = []
        
        # 1. Add template image if requested
        context_images = data.get('context_images', {})
        if isinstance(context_images, dict):
            use_template = context_images.get('use_template', False)
        else:
            use_template = data.get('use_template', False)
        
        if use_template:
            template_path = file_service.get_template_path(project_id)
            if template_path:
                additional_ref_images.append(template_path)
        
        # 2. Add desc image URLs if provided
        if isinstance(context_images, dict):
            desc_image_urls = context_images.get('desc_image_urls', [])
        else:
            desc_image_urls = data.get('desc_image_urls', [])
        
        if desc_image_urls:
            if isinstance(desc_image_urls, list):
                additional_ref_images.extend(desc_image_urls)
        
        # 3. For FastAPI, we'll handle file uploads differently
        temp_dir = None
        
        # Create async task for image editing
        task = Task(
            project_id=project_id,
            task_type='EDIT_PAGE_IMAGE',
            status='PENDING'
        )
        task.set_progress({
            'total': 1,
            'completed': 0,
            'failed': 0
        })
        db.add(task)
        db.commit()
        
        # Submit background task
        from main import app  # Import the app instance
        task_manager.submit_task(
            task.id,
            edit_page_image_task,
            project_id,
            page_id,
            data['edit_instruction'],
            ai_service,
            file_service,
            os.getenv('DEFAULT_ASPECT_RATIO', '16:9'),
            os.getenv('DEFAULT_RESOLUTION', '2K'),
            original_description,
            additional_ref_images if additional_ref_images else None,
            str(temp_dir) if temp_dir else None,
            app
        )
        
        # Return task_id immediately
        return success_response({
            'task_id': task.id,
            'page_id': page_id,
            'status': 'PENDING'
        }, status_code=202)
    
    except Exception as e:
        db.rollback()
        return error_response('AI_SERVICE_ERROR', str(e), 503)



@page_router.get('/{project_id}/pages/{page_id}/image-versions')
async def get_page_image_versions(project_id: str, page_id: str):
    """
    Get all image versions for a page
    """
    try:
        # Use session to query
        page = db.query(Page).filter(Page.id == page_id).first()
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        # Use session to query
        versions = db.query(PageImageVersion).filter(PageImageVersion.page_id == page_id)\
            .order_by(PageImageVersion.version_number.desc()).all()
        
        return success_response({
            'versions': [v.to_dict() for v in versions]
        })
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@page_router.post('/{project_id}/pages/{page_id}/image-versions/{version_id}/set-current')
async def set_current_image_version(project_id: str, page_id: str, version_id: str):
    """
    Set a specific version as the current one
    """
    try:
        # Use session to query
        page = db.query(Page).filter(Page.id == page_id).first()
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        # Use session to query
        version = db.query(PageImageVersion).filter(PageImageVersion.id == version_id).first()
        
        if not version or version.page_id != page_id:
            return not_found('Image Version')
        
        # Mark all versions as not current
        db.query(PageImageVersion).filter(PageImageVersion.page_id == page_id).update({'is_current': False})
        
        # Set this version as current
        version.is_current = True
        page.generated_image_path = version.image_path
        page.updated_at = datetime.utcnow()
        
        db.commit()
        
        return success_response(page.to_dict(include_versions=True))
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)
