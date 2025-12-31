"""
Material Controller - handles standalone material image generation
"""
from fastapi import APIRouter, Request, UploadFile, File
from models import db, Project, Material, Task
from utils import success_response, error_response, not_found, bad_request
from services import AIService, FileService
from services.task_manager import task_manager, generate_material_image_task
from pathlib import Path
from werkzeug.utils import secure_filename
from typing import Optional
import tempfile
import shutil
import time
import os


material_router = APIRouter()
material_global_router = APIRouter(prefix='/api/materials')

ALLOWED_MATERIAL_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}


def _build_material_query(filter_project_id: str):
    """Build common material query with project validation."""
    query = db.query(Material)

    if filter_project_id == 'all':
        return query, None
    if filter_project_id == 'none':
        return query.filter(Material.project_id.is_(None)), None

    project = db.query(Project).filter(Project.id == filter_project_id).first()
    if not project:
        return None, not_found('Project')

    return query.filter(Material.project_id == filter_project_id), None


def _get_materials_list(filter_project_id: str):
    """
    Common logic to get materials list.
    Returns (materials_list, error_response)
    """
    query, error = _build_material_query(filter_project_id)
    if error:
        return None, error
    
    materials = query.order_by(Material.created_at.desc()).all()
    materials_list = [material.to_dict() for material in materials]
    
    return materials_list, None


def _handle_material_upload(default_project_id: Optional[str] = None):
    """
    Common logic to handle material upload.
    Returns Flask response object.
    This function is kept for backward compatibility but not used in FastAPI.
    """
    # This function is not used in FastAPI implementation
    # It's kept for backward compatibility with Flask code
    pass


def _resolve_target_project_id(raw_project_id: Optional[str], allow_none: bool = True):
    """
    Normalize project_id from request.
    Returns (project_id | None, error_response | None)
    """
    if allow_none and (raw_project_id is None or raw_project_id == 'none'):
        return None, None

    if raw_project_id == 'all':
        return None, bad_request("project_id cannot be 'all' when uploading materials")

    if raw_project_id:
        project = db.query(Project).filter(Project.id == raw_project_id).first()
        if not project:
            return None, not_found('Project')

    return raw_project_id, None


async def _save_material_file_fastapi(file: UploadFile, target_project_id: Optional[str]):
    """Shared logic for saving uploaded material files to disk and DB in FastAPI context."""
    if not file or not file.filename:
        return None, bad_request("file is required")

    filename = secure_filename(file.filename)
    file_ext = Path(filename).suffix.lower()
    if file_ext not in ALLOWED_MATERIAL_EXTENSIONS:
        return None, bad_request(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_MATERIAL_EXTENSIONS))}")

    upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
    file_service = FileService(upload_folder)
    if target_project_id:
        materials_dir = file_service._get_materials_dir(target_project_id)
    else:
        materials_dir = file_service.upload_folder / "materials"
        materials_dir.mkdir(exist_ok=True, parents=True)

    timestamp = int(time.time() * 1000)
    base_name = Path(filename).stem
    unique_filename = f"{base_name}_{timestamp}{file_ext}"

    filepath = materials_dir / unique_filename
    
    # Save file content
    file_content = await file.read()
    with open(str(filepath), 'wb') as f:
        f.write(file_content)

    relative_path = str(filepath.relative_to(file_service.upload_folder))
    if target_project_id:
        image_url = file_service.get_file_url(target_project_id, 'materials', unique_filename)
    else:
        image_url = f"/files/materials/{unique_filename}"

    material = Material(
        project_id=target_project_id,
        filename=unique_filename,
        relative_path=relative_path,
        url=image_url
    )

    try:
        db.add(material)
        db.commit()
        return material, None
    except Exception:
        db.rollback()
        raise


@material_router.post('/{project_id}/materials/generate')
async def generate_material_image(project_id: str, request: Request):
    """
    Generate a standalone material image

    Supports multipart/form-data:
    - prompt: Text-to-image prompt (passed directly to the model without modification)
    - ref_image: Main reference image (optional)
    - extra_images: Additional reference images (multiple files, optional)
    
    Note: project_id can be 'none' to generate global materials (not associated with any project)
    """
    try:
        # 支持 'none' 作为特殊值，表示生成全局素材
        if project_id != 'none':
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return not_found('Project')
        else:
            project = None
            project_id = None  # 设置为None表示全局素材

        # Parse request data (for FastAPI we'll handle this differently)
        data = await request.json() or {}
        prompt = data.get('prompt', '').strip()
        
        if not prompt:
            return bad_request("prompt is required")

        # 处理project_id：对于全局素材，使用'global'作为Task的project_id
        # Task模型要求project_id不能为null，但Material可以
        task_project_id = project_id if project_id is not None else 'global'
        
        # 验证project_id（如果不是'global'）
        if task_project_id != 'global':
            project = db.query(Project).filter(Project.id == task_project_id).first()
            if not project:
                return not_found('Project')

        # Initialize services
        ai_service = AIService()
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)

        # 创建临时目录保存参考图片（后台任务会清理）
        temp_dir = Path(tempfile.mkdtemp(dir=upload_folder))
        temp_dir_str = str(temp_dir)

        try:
            # For FastAPI, we'll handle files differently - this is a simplified version
            # In a real implementation, you'd use UploadFile parameters
            ref_path_str = None
            additional_ref_images = []

            # Create async task for material generation
            task = Task(
                project_id=task_project_id,
                task_type='GENERATE_MATERIAL',
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
                generate_material_image_task,
                task_project_id,  # 传递给任务函数，它会处理'global'的情况
                prompt,
                ai_service,
                file_service,
                ref_path_str,
                additional_ref_images if additional_ref_images else None,
                os.getenv('DEFAULT_ASPECT_RATIO', '16:9'),
                os.getenv('DEFAULT_RESOLUTION', '2K'),
                temp_dir_str,
                app
            )

            # Return task_id immediately (不再清理temp_dir，由后台任务清理)
            return success_response({
                'task_id': task.id,
                'status': 'PENDING'
            }, status_code=202)
        
        except Exception as e:
            # Clean up temp directory on error
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    except Exception as e:
        db.rollback()
        return error_response('AI_SERVICE_ERROR', str(e), 503)


@material_router.get('/{project_id}/materials')
async def list_materials(project_id: str):
    """
    List materials for a specific project
    
    Returns:
        List of material images with filename, url, and metadata for the specified project
    """
    try:
        materials_list, error = _get_materials_list(project_id)
        if error:
            return error
        
        return success_response({
            "materials": materials_list,
            "count": len(materials_list)
        })
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@material_router.post('/{project_id}/materials/upload')
async def upload_material(project_id: str, file: UploadFile = File(...)):
    """
    Upload a material image
    
    Supports multipart/form-data:
    - file: Image file (required)
    - project_id: Optional query parameter, defaults to path parameter if not provided
    
    Returns:
        Material info with filename, url, and metadata
    """
    try:
        # Validate project exists
        if project_id != 'none':
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return not_found('Project')
        else:
            project_id = None

        # Get file content
        file_content = await file.read()
        filename = file.filename or "unknown"
        
        # Validate file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in ALLOWED_MATERIAL_EXTENSIONS:
            return bad_request(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_MATERIAL_EXTENSIONS))}")

        # Save file to disk
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        
        if project_id:
            materials_dir = file_service._get_materials_dir(project_id)
        else:
            materials_dir = file_service.upload_folder / "materials"
            materials_dir.mkdir(exist_ok=True, parents=True)

        timestamp = int(time.time() * 1000)
        base_name = Path(filename).stem
        unique_filename = f"{base_name}_{timestamp}{file_ext}"

        filepath = materials_dir / unique_filename
        
        # Write file content
        with open(filepath, 'wb') as f:
            f.write(file_content)

        relative_path = str(filepath.relative_to(file_service.upload_folder))
        if project_id:
            image_url = file_service.get_file_url(project_id, 'materials', unique_filename)
        else:
            image_url = f"/files/materials/{unique_filename}"

        material = Material(
            project_id=project_id,
            filename=unique_filename,
            relative_path=relative_path,
            url=image_url
        )

        try:
            db.add(material)
            db.commit()
            return success_response(material.to_dict(), status_code=201)
        except Exception:
            db.rollback()
            raise
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@material_global_router.get('')
async def list_all_materials(request: Request):
    """
    Global materials endpoint for complex queries
    
    Query params:
        - project_id: Filter by project_id
          * 'all' (default): Get all materials regardless of project
          * 'none': Get only materials without a project (global materials)
          * <project_id>: Get materials for specific project
    
    Returns:
        List of material images with filename, url, and metadata
    """
    try:
        query_params = dict(request.query_params)
        filter_project_id = query_params.get('project_id', 'all')
        materials_list, error = _get_materials_list(filter_project_id)
        if error:
            return error
        
        return success_response({
            "materials": materials_list,
            "count": len(materials_list)
        })
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@material_global_router.post('/upload')
async def upload_material_global(file: UploadFile = File(...), project_id: str = None):
    """
    Upload a material image (global, not bound to a project)
    
    Supports multipart/form-data:
    - file: Image file (required)
    - project_id: Optional query parameter to associate with a project
    
    Returns:
        Material info with filename, url, and metadata
    """
    try:
        # Validate project if project_id is provided
        if project_id and project_id != 'none':
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return not_found('Project')
        elif project_id == 'none':
            project_id = None

        # Get file content
        file_content = await file.read()
        filename = file.filename or "unknown"
        
        # Validate file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in ALLOWED_MATERIAL_EXTENSIONS:
            return bad_request(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_MATERIAL_EXTENSIONS))}")

        # Save file to disk
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        
        if project_id:
            materials_dir = file_service._get_materials_dir(project_id)
        else:
            materials_dir = file_service.upload_folder / "materials"
            materials_dir.mkdir(exist_ok=True, parents=True)

        timestamp = int(time.time() * 1000)
        base_name = Path(filename).stem
        unique_filename = f"{base_name}_{timestamp}{file_ext}"

        filepath = materials_dir / unique_filename
        
        # Write file content
        with open(filepath, 'wb') as f:
            f.write(file_content)

        relative_path = str(filepath.relative_to(file_service.upload_folder))
        if project_id:
            image_url = file_service.get_file_url(project_id, 'materials', unique_filename)
        else:
            image_url = f"/files/materials/{unique_filename}"

        material = Material(
            project_id=project_id,
            filename=unique_filename,
            relative_path=relative_path,
            url=image_url
        )

        try:
            db.add(material)
            db.commit()
            return success_response(material.to_dict(), status_code=201)
        except Exception:
            db.rollback()
            raise
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@material_global_router.delete('/{material_id}')
async def delete_material(material_id: str):
    """
    Delete a material and its file
    """
    try:
        material = db.get(Material, material_id)
        if not material:
            return not_found('Material')

        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_service = FileService(upload_folder)
        material_path = Path(file_service.get_absolute_path(material.relative_path))

        # First, delete the database record to ensure data consistency
        db.delete(material)
        db.commit()

        # Then, attempt to delete the file. If this fails, log the error
        # but still return a success response. This leaves an orphan file,
        try:
            if material_path.exists():
                material_path.unlink(missing_ok=True)
        except OSError as e:
            # For FastAPI, we'll just print the warning instead of using Flask's logger
            print(f"Failed to delete file for material {material_id} at {material_path}: {e}")

        return success_response({"id": material_id})
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@material_global_router.post('/associate')
async def associate_materials_to_project(request: Request):
    """
    Associate materials to a project by URLs
    
    Request body (JSON):
    {
        "project_id": "project_id",
        "material_urls": ["url1", "url2", ...]
    }
    
    Returns:
        List of associated material IDs and count
    """
    try:
        data = await request.json() or {}
        project_id = data.get('project_id')
        material_urls = data.get('material_urls', [])
        
        if not project_id:
            return bad_request("project_id is required")
        
        if not material_urls or not isinstance(material_urls, list):
            return bad_request("material_urls must be a non-empty array")
        
        # Validate project exists
        project = db.get(Project, project_id)
        if not project:
            return not_found('Project')
        
        # Find materials by URLs and update their project_id
        updated_ids = []
        materials_to_update = db.query(Material).filter(
            Material.url.in_(material_urls),
            Material.project_id.is_(None)
        ).all()
        for material in materials_to_update:
            material.project_id = project_id
            updated_ids.append(material.id)
        
        db.commit()
        
        return success_response({
            "updated_ids": updated_ids,
            "count": len(updated_ids)
        })
    
    except Exception as e:
        db.rollback()
        return error_response('SERVER_ERROR', str(e), 500)

