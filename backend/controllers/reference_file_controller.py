"""
Reference File Controller - handles file upload and parsing
"""
import os
import logging
import re
import uuid
from fastapi import APIRouter, Request, UploadFile, File
from werkzeug.utils import secure_filename
from pathlib import Path
from config import Config
from datetime import datetime
from urllib.parse import unquote
import threading

from models import db, ReferenceFile, Project
from utils.response import success_response, error_response, bad_request, not_found
from services.file_parser_service import FileParserService

logger = logging.getLogger(__name__)

reference_file_router = APIRouter(prefix='/api/reference-files')


@reference_file_router.get('')
async def list_reference_files(request: Request):
    """
    Get all reference files or filter by project_id
    """
    try:
        query_params = dict(request.query_params)
        project_id = query_params.get('project_id')

        if project_id:
            reference_files = db.query(ReferenceFile).filter(
                ReferenceFile.project_id == project_id
            ).order_by(ReferenceFile.created_at.desc()).all()
        else:
            reference_files = db.query(ReferenceFile).order_by(ReferenceFile.created_at.desc()).all()

        reference_files_list = [rf.to_dict() for rf in reference_files]

        return success_response({
            "reference_files": reference_files_list,
            "count": len(reference_files_list)
        })

    except Exception as e:
        logger.error(f"list_reference_files failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@reference_file_router.get('/project/{project_id}')
async def get_reference_files_by_project(project_id: str):
    """
    Get reference files for a specific project
    """
    try:
        # Import here to avoid circular imports
        from models import ReferenceFile

        # Query reference files for this project
        reference_files = db.query(ReferenceFile).filter(
            ReferenceFile.project_id == project_id
        ).order_by(ReferenceFile.created_at.desc()).all()

        reference_files_list = [rf.to_dict() for rf in reference_files]

        return success_response({
            "reference_files": reference_files_list,
            "count": len(reference_files_list)
        })

    except Exception as e:
        logger.error(f"get_reference_files_by_project failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


def _allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def _get_file_type(filename: str) -> str:
    """Get file type from filename"""
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return 'unknown'


def _parse_file_async(file_id: str, file_path: str, filename: str, app):
    """
    Parse file asynchronously in background
    
    Args:
        file_id: Reference file ID
        file_path: Path to the uploaded file
        filename: Original filename
        app: FastAPI app instance
    """
    try:
        reference_file = db.query(ReferenceFile).filter(ReferenceFile.id == file_id).first()
        if not reference_file:
            logger.error(f"Reference file {file_id} not found")
            return
        
        # Update status to parsing
        reference_file.parse_status = 'parsing'
        db.commit()
        
        # Initialize parser service with environment variables
        parser = FileParserService(
            mineru_token=os.getenv('MINERU_TOKEN', ''),
            mineru_api_base=os.getenv('MINERU_API_BASE', ''),
            google_api_key=os.getenv('GOOGLE_API_KEY', ''),
            google_api_base=os.getenv('GOOGLE_API_BASE', ''),
            openai_api_key=os.getenv('OPENAI_API_KEY', ''),
            openai_api_base=os.getenv('OPENAI_API_BASE', ''),
            image_caption_model=os.getenv('IMAGE_CAPTION_MODEL', 'gemini-3-flash-preview'),
            provider_format=os.getenv('AI_PROVIDER_FORMAT', 'gemini')
        )
        
        # Parse file
        logger.info(f"Starting to parse file: {filename}")
        batch_id, markdown_content, extract_id, error_message, failed_image_count = parser.parse_file(file_path, filename)
        
        # Update database
        reference_file.mineru_batch_id = batch_id
        if error_message:
            reference_file.parse_status = 'failed'
            reference_file.error_message = error_message
            logger.error(f"File parsing failed: {error_message}")
        else:
            reference_file.parse_status = 'completed'
            reference_file.markdown_content = markdown_content
            if failed_image_count > 0:
                logger.warning(f"File parsing completed: {filename}, but {failed_image_count} images failed to generate captions")
            else:
                logger.info(f"File parsing completed: {filename}")
        
        reference_file.updated_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        logger.error(f"Error in async file parsing: {str(e)}", exc_info=True)
        try:
            reference_file = db.query(ReferenceFile).filter(ReferenceFile.id == file_id).first()
            if reference_file:
                reference_file.parse_status = 'failed'
                reference_file.error_message = f"Parsing error: {str(e)}"
                reference_file.updated_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update error status: {str(db_error)}")


@reference_file_router.post('/upload')
async def upload_reference_file(request: Request, file: UploadFile = File(...), project_id: str = None):
    """
    POST /api/reference-files/upload - Upload a reference file
    
    Supports multipart/form-data:
    - file: The file to upload (required)
    - project_id: Project ID to associate with (optional, 'none' for global files)
    
    Returns:
        Reference file information with status
    """
    try:
        # Get filename - handle encoding issues with non-ASCII characters
        original_filename = file.filename
        if not original_filename or original_filename == '':
            # Try to get filename from Content-Disposition header
            content_disposition = request.headers.get('Content-Disposition', '')
            if content_disposition:
                filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition)
                if filename_match:
                    original_filename = filename_match.group(1).strip('"\'')
                    # Decode if URL encoded
                    try:
                        original_filename = unquote(original_filename)
                    except:
                        pass
        
        if not original_filename or original_filename == '':
            return bad_request("No file selected or filename could not be determined")
        
        logger.info(f"Received file upload: {original_filename}")
        
        # Check file extension
        allowed_extensions = set(Config.ALLOWED_REFERENCE_FILE_EXTENSIONS)
        if not _allowed_file(original_filename, allowed_extensions):
            return bad_request(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}")
        
        # Process project_id (optional)
        if project_id == 'none' or not project_id:
            project_id = None
        else:
            # Verify project exists
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return not_found('Project')
        
        # Secure filename for filesystem (but keep original for database)
        # secure_filename removes non-ASCII chars, so we need to handle Chinese characters
        filename = secure_filename(original_filename)
        
        # If secure_filename removed everything (e.g., all Chinese chars), use a fallback
        if not filename or filename == '':
            # Extract extension from original filename
            ext = _get_file_type(original_filename)
            if ext == 'unknown':
                ext = 'file'
            filename = f"file_{uuid.uuid4().hex[:8]}.{ext}"
            logger.warning(f"Original filename '{original_filename}' was sanitized to '{filename}'")
        
        # Create upload directory structure
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        reference_files_dir = Path(upload_folder) / 'reference_files'
        reference_files_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        file_type = _get_file_type(original_filename)  # Use original filename for type detection
        unique_filename = f"{unique_id}_{filename}"
        file_path = reference_files_dir / unique_filename
        
        # Save file content
        file_content = await file.read()
        with open(str(file_path), 'wb') as f:
            f.write(file_content)
        file_size = len(file_content)
        
        # Create database record
        reference_file = ReferenceFile(
            project_id=project_id,
            filename=original_filename,
            file_path=str(file_path.relative_to(upload_folder)),
            file_size=file_size,
            file_type=file_type,
            parse_status='pending'
        )
        
        db.add(reference_file)
        db.commit()
        
        logger.info(f"File uploaded: {original_filename} (ID: {reference_file.id})")
        
        # Start background parsing thread
        # Use threading to avoid blocking the response
        from main import app  # Import the app instance
        thread = threading.Thread(
            target=_parse_file_async,
            args=(reference_file.id, str(file_path), original_filename, app)
        )
        thread.daemon = True
        thread.start()
        
        return success_response(
            data=reference_file.to_dict(),
            message="File uploaded successfully, parsing started",
            status_code=201
        )
        
    except Exception as e:
        logger.error(f"Error uploading reference file: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@reference_file_router.get('/{file_id}')
async def get_reference_file(file_id: str):
    """
    Get reference file information
    
    Returns:
        Reference file information including parse status
    """
    try:
        reference_file = db.query(ReferenceFile).filter(ReferenceFile.id == file_id).first()
        if not reference_file:
            return not_found('Reference file')
        
        # 单个文件查询时包含内容和失败计数（会在 to_dict 中根据状态判断是否计算）
        return success_response({'file': reference_file.to_dict(include_content=True, include_failed_count=True)})
        
    except Exception as e:
        logger.error(f"Error getting reference file: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@reference_file_router.delete('/{file_id}')
async def delete_reference_file(file_id: str):
    """
    Delete a reference file
    
    Returns:
        Success message
    """
    try:
        reference_file = db.query(ReferenceFile).filter(ReferenceFile.id == file_id).first()
        if not reference_file:
            return not_found('Reference file')
        
        # Delete file from disk
        try:
            upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
            file_path = Path(upload_folder) / reference_file.file_path
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file from disk: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file from disk: {str(e)}")
        
        # Delete from database
        db.delete(reference_file)
        db.commit()
        
        logger.info(f"Deleted reference file: {file_id}")
        
        return success_response({'message': 'File deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting reference file: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@reference_file_router.get('/project/{project_id}')
async def list_project_reference_files(project_id: str):
    """
    List all reference files for a project
    
    Special values:
    - 'all': List all reference files (global + all projects)
    - 'global' or 'none': List only global files (not associated with any project)
    - project_id: List files for specific project
    
    Returns:
        List of reference files
    """
    try:
        # Special case: 'all' means list all files
        if project_id == 'all':
            reference_files = db.query(ReferenceFile).all()
        # Special case: 'global' or 'none' means list global files (not associated with any project)
        elif project_id in ['global', 'none']:
            reference_files = db.query(ReferenceFile).filter(ReferenceFile.project_id.is_(None)).all()
        else:
            # Verify project exists
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return not_found('Project')
            
            reference_files = db.query(ReferenceFile).filter(ReferenceFile.project_id == project_id).all()
        
        # 列表查询时不包含 markdown_content 和失败计数，加快响应速度
        return success_response({
            'files': [f.to_dict(include_content=False) for f in reference_files]
        })
        
    except Exception as e:
        logger.error(f"Error listing reference files: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@reference_file_router.post('/{file_id}/parse')
async def trigger_file_parse(file_id: str):
    """
    Trigger parsing for a reference file
    
    Returns:
        Updated reference file information
    """
    try:
        reference_file = db.query(ReferenceFile).filter(ReferenceFile.id == file_id).first()
        if not reference_file:
            return not_found('Reference file')
        
        # 如果正在解析，直接返回
        if reference_file.parse_status == 'parsing':
            return success_response({
                'file': reference_file.to_dict(),
                'message': 'File is already being parsed'
            })
        
        # 如果解析完成或失败，可以重新解析
        if reference_file.parse_status in ['completed', 'failed']:
            reference_file.parse_status = 'pending'
            reference_file.error_message = None
            # 清空之前的解析结果，以便重新解析
            reference_file.markdown_content = None
            reference_file.mineru_batch_id = None
            db.commit()
        
        # 获取文件路径
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_path = Path(upload_folder) / reference_file.file_path
        
        if not file_path.exists():
            return error_response('FILE_NOT_FOUND', f'File not found: {file_path}', 404)
        
        # 启动异步解析
        from main import app  # Import the app instance
        thread = threading.Thread(
            target=_parse_file_async,
            args=(reference_file.id, str(file_path), reference_file.filename, app)
        )
        thread.daemon = True
        thread.start()
        
        logger.info(f"Triggered parsing for file: {reference_file.filename} (ID: {file_id})")
        
        return success_response({
            'file': reference_file.to_dict(),
            'message': 'Parsing started'
        })
        
    except Exception as e:
        logger.error(f"Error triggering file parse: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@reference_file_router.post('/{file_id}/associate')
async def associate_file_to_project(file_id: str, request: Request):
    """
    Associate a reference file to a project
    
    Request body:
    {
        "project_id": "project-id-here"
    }
    
    Returns:
        Updated reference file information
    """
    try:
        reference_file = db.query(ReferenceFile).filter(ReferenceFile.id == file_id).first()
        if not reference_file:
            return not_found('Reference file')
        
        data = await request.json() or {}
        project_id = data.get('project_id')
        
        if not project_id:
            return bad_request("project_id is required")
        
        # Verify project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return not_found('Project')
        
        # Update file's project_id
        reference_file.project_id = project_id
        reference_file.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Associated reference file {file_id} to project {project_id}")
        
        return success_response({'file': reference_file.to_dict()})
        
    except Exception as e:
        logger.error(f"Error associating reference file: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@reference_file_router.post('/{file_id}/dissociate')
async def dissociate_file_from_project(file_id: str):
    """
    Remove a reference file from its project
    
    This sets the file's project_id to None, effectively making it a global file.
    The file itself is not deleted.
    
    Returns:
        Updated reference file information
    """
    try:
        reference_file = db.query(ReferenceFile).filter(ReferenceFile.id == file_id).first()
        if not reference_file:
            return not_found('Reference file')
        
        # Remove project association
        reference_file.project_id = None
        reference_file.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Dissociated reference file {file_id} from project")
        
        return success_response({'file': reference_file.to_dict(), 'message': 'File removed from project'})
        
    except Exception as e:
        logger.error(f"Error dissociating reference file: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)

