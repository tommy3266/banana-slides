"""
File Controller - handles static file serving
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from utils import error_response, not_found
from utils.path_utils import find_file_with_prefix
import os
from pathlib import Path
from werkzeug.utils import secure_filename
import os

file_router = APIRouter(prefix='/files')


@file_router.get('/{project_id}/{file_type}/{filename}')
async def serve_file(project_id: str, file_type: str, filename: str):
    """
    Serve static files
    
    Args:
        project_id: Project UUID
        file_type: 'template' or 'pages'
        filename: File name
    """
    try:
        if file_type not in ['template', 'pages', 'materials', 'exports']:
            return not_found('File')
        
        # Construct file path
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_dir = os.path.join(
            upload_folder,
            project_id,
            file_type
        )
        
        # Check if directory exists
        if not os.path.exists(file_dir):
            return not_found('File')
        
        # Check if file exists
        file_path = os.path.join(file_dir, filename)
        if not os.path.exists(file_path):
            return not_found('File')
        
        # Serve file
        return FileResponse(file_path)
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@file_router.get('/user-templates/{template_id}/{filename}')
async def serve_user_template(template_id: str, filename: str):
    """
    Serve user template files
    
    Args:
        template_id: Template UUID
        filename: File name
    """
    try:
        # Construct file path
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_dir = os.path.join(
            upload_folder,
            'user-templates',
            template_id
        )
        
        # Check if directory exists
        if not os.path.exists(file_dir):
            return not_found('File')
        
        # Check if file exists
        file_path = os.path.join(file_dir, filename)
        if not os.path.exists(file_path):
            return not_found('File')
        
        # Serve file
        return FileResponse(file_path)
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@file_router.get('/materials/{filename}')
async def serve_global_material(filename: str):
    """
    Serve global material files (not bound to a project)
    
    Args:
        filename: File name
    """
    try:
        safe_filename = secure_filename(filename)
        # Construct file path
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        file_dir = os.path.join(
            upload_folder,
            'materials'
        )
        
        # Check if directory exists
        if not os.path.exists(file_dir):
            return not_found('File')
        
        # Check if file exists
        file_path = os.path.join(file_dir, safe_filename)
        if not os.path.exists(file_path):
            return not_found('File')
        
        # Serve file
        return FileResponse(file_path)
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@file_router.get('/mineru/{extract_id}/{filepath:path}')
async def serve_mineru_file(extract_id: str, filepath: str):
    """
    Serve MinerU extracted files.

    Args:
        extract_id: Extract UUID
        filepath: Relative file path within the extract
    """
    try:
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        root_dir = os.path.join(upload_folder, 'mineru_files', extract_id)
        full_path = Path(root_dir) / filepath

        # This prevents path traversal attacks
        resolved_root_dir = Path(root_dir).resolve()
        
        try:
            # Check if the path is trying to escape the root directory
            resolved_full_path = full_path.resolve()
            if not str(resolved_full_path).startswith(str(resolved_root_dir)):
                return error_response('INVALID_PATH', 'Invalid file path', 403)
        except Exception:
            # If we can't resolve the path at all, it's invalid
            return error_response('INVALID_PATH', 'Invalid file path', 403)

        # Try to find file with prefix matching
        matched_path = find_file_with_prefix(full_path)
        
        if matched_path is not None:
            # Additional security check for matched path
            try:
                resolved_matched_path = matched_path.resolve(strict=True)
                
                # Verify the matched file is still within the root directory
                if not str(resolved_matched_path).startswith(str(resolved_root_dir)):
                    return error_response('INVALID_PATH', 'Invalid file path', 403)
            except FileNotFoundError:
                return not_found('File')
            except Exception:
                return error_response('INVALID_PATH', 'Invalid file path', 403)
            
            return FileResponse(str(matched_path))

        return not_found('File')
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)

