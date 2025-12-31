"""
FastAPI Application Entry Point
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
from sqlalchemy.exc import SQLAlchemyError

# Load environment variables from project root .env file
_project_root = Path(__file__).parent.parent
_env_file = _project_root / '.env'
load_dotenv(dotenv_path=_env_file, override=True)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

# Import the database engine for initialization
from models import engine, Base
from config import Config

# Enable SQLite WAL mode for all connections
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Enable WAL mode and related PRAGMAs for each SQLite connection.
    Registered once at import time to avoid duplicate handlers when
    create_app() is called multiple times.
    """
    # Only apply to SQLite connections
    if not isinstance(dbapi_conn, sqlite3.Connection):
        return

    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds timeout
    finally:
        cursor.close()


def create_app():
    """Application factory"""
    app = FastAPI(
        title='Banana Slides API',
        description='AI-powered PPT generation service API documentation',
        version='1.0.0',
        docs_url="/api-docs/",  # Swagger UI
        redoc_url="/api-redoc/"  # ReDoc
    )
    
    # Load configuration from Config class
    # Configuration will be accessed via environment variables or Config class
    
    # Override with environment-specific paths (use absolute path)
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    instance_dir = os.path.join(backend_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    db_path = os.path.join(instance_dir, 'database.db')
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
    
    # Ensure upload folder exists
    project_root = os.path.dirname(backend_dir)
    upload_folder = os.path.join(project_root, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    os.environ['UPLOAD_FOLDER'] = upload_folder
    
    # CORS configuration (parse from environment)
    raw_cors = os.getenv('CORS_ORIGINS', 'http://localhost:3000')
    if raw_cors.strip() == '*':
        cors_origins = ['*']
    else:
        cors_origins = [o.strip() for o in raw_cors.split(',') if o.strip()]
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Add any additional allowed headers if needed
        # expose_headers=["Access-Control-Allow-Origin"]
    )
    
    # Initialize logging (log to stdout so Docker can capture it)
    log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO'), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # 设置第三方库的日志级别，避免过多的DEBUG日志
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Include all routers
    from controllers.material_controller import material_router, material_global_router
    from controllers.reference_file_controller import reference_file_router
    from controllers.settings_controller import settings_router
    from controllers.project_controller import project_router
    from controllers.page_controller import page_router
    from controllers.template_controller import template_router, user_template_router
    from controllers.export_controller import export_router
    from controllers.file_controller import file_router
    
    app.include_router(project_router, prefix="/api/projects", tags=["projects"])
    app.include_router(page_router, prefix="/api/projects", tags=["pages"])
    app.include_router(template_router, prefix="/api/templates", tags=["templates"])
    app.include_router(user_template_router, tags=["user-templates"])
    app.include_router(export_router, prefix="/api/export", tags=["export"])
    app.include_router(file_router, tags=["files"])
    app.include_router(material_router, prefix="/api/materials", tags=["materials"])
    app.include_router(material_global_router, tags=["materials-global"])
    app.include_router(reference_file_router, tags=["reference-files"])
    app.include_router(settings_router, tags=["settings"])

    # Health check endpoint
    @app.get('/health', tags=["health"])
    def health_check():
        return {'status': 'ok', 'message': 'Banana Slides API is running'}
    
    # Output language endpoint
    @app.get('/api/output-language', tags=["settings"])
    def get_output_language():
        """
        获取用户的输出语言偏好（从数据库 Settings 读取）
        返回: zh, ja, en, auto
        """
        from models import Settings
        try:
            settings = Settings.get_settings()
            return {'data': {'language': settings.output_language}}
        except SQLAlchemyError as db_error:
            logging.warning(f"Failed to load output language from settings: {db_error}")
            return {'data': {'language': Config.OUTPUT_LANGUAGE}}  # 默认中文

    # Root endpoint
    @app.get('/', tags=["root"])
    def index():
        return {
            'name': 'Banana Slides API',
            'version': '1.0.0',
            'description': 'AI-powered PPT generation service',
            'endpoints': {
                'health': '/health',
                'api_docs': '/api-docs/',
                'api_redoc': '/api-redoc/',
                'projects': '/api/projects'
            }
        }
    
    return app


def custom_openapi():
    """Customize the OpenAPI schema to add security schemes"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Banana Slides API",
        version="1.0.0",
        description="AI-powered PPT generation service API documentation",
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"] = {"securitySchemes": {
        "Bearer": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Enter: Bearer {token}"
        }
    }}
    
    # Apply security globally
    openapi_schema["security"] = [{"Bearer": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Create app instance
app = create_app()
app.openapi = custom_openapi  # Override the default openapi method


if __name__ == '__main__':
    # Run development server with uvicorn
    import uvicorn
    if os.getenv("IN_DOCKER", "0") == "1":
        port = 5001  # 在 docker 内部部署时始终使用 5001 端口
    else:
        port = int(os.getenv('PORT', 5001))
    debug = os.getenv('FASTAPI_ENV', 'development') == 'development'
    
    logging.info(
        "\n"
        "╔══════════════════════════════════════╗\n"
        "║   🍌 Banana Slides API Server 🍌   ║\n"
        "╚══════════════════════════════════════╝\n"
        f"Server starting on: http://localhost:{port}\n"
        f"Output Language: {os.getenv('OUTPUT_LANGUAGE', 'zh')}\n"
        f"Environment: {os.getenv('FASTAPI_ENV', 'development')}\n"
        f"Debug mode: {debug}\n"
        f"API Base URL: http://localhost:{port}/api\n"
        f"Database: {os.getenv('DATABASE_URL', 'sqlite:///instance/database.db')}\n"
        f"Uploads: {os.getenv('UPLOAD_FOLDER', 'uploads')}"
    )
    
    uvicorn.run(app, host='0.0.0.0', port=port)