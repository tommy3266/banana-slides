from pydantic import BaseModel, Field
from typing import Optional, List, Union, Tuple
from fastapi import Body


class CreateProjectRequest(BaseModel):
    creation_type: str = Body(default="idea", description="项目创建类型", example="idea")
    idea_prompt: Optional[str] = Body(None, description="创意提示", example="创建一个关于人工智能的演示文稿")
    outline_text: Optional[str] = Body(None, description="大纲文本", example="1. 介绍\n2. 主要内容\n3. 结论")
    description_text: Optional[str] = Body(None, description="描述文本", example="这是一个关于人工智能的详细演示文稿...")
    template_style: Optional[str] = Body(None, description="模板风格", example="现代简约风格")


class UpdateProjectRequest(BaseModel):
    idea_prompt: Optional[str] = None
    extra_requirements: Optional[str] = None
    template_style: Optional[str] = None
    pages_order: Optional[List[str]] = None


class GenerateOutlineRequest(BaseModel):
    idea_prompt: Optional[str] = None
    language: Optional[str] = None


class GenerateFromDescriptionRequest(BaseModel):
    description_text: Optional[str] = None
    language: Optional[str] = None


class GenerateDescriptionsRequest(BaseModel):
    max_workers: Optional[int] = None
    language: Optional[str] = None


class GenerateImagesRequest(BaseModel):
    max_workers: Optional[int] = None
    use_template: Optional[bool] = None
    language: Optional[str] = None


class RefineOutlineRequest(BaseModel):
    user_requirement: str
    previous_requirements: Optional[List[str]] = None
    language: Optional[str] = None


class RefineDescriptionsRequest(BaseModel):
    user_requirement: str
    previous_requirements: Optional[List[str]] = None
    language: Optional[str] = None


class CreatePageRequest(BaseModel):
    order_index: int
    part: Optional[str] = None
    outline_content: Optional[dict] = None


class UpdatePageOutlineRequest(BaseModel):
    outline_content: dict


class UpdatePageDescriptionRequest(BaseModel):
    description_content: dict


class UpdateSettingsRequest(BaseModel):
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    image_resolution: Optional[str] = None
    image_aspect_ratio: Optional[str] = None
    max_description_workers: Optional[int] = None
    max_image_workers: Optional[int] = None
    text_model: Optional[str] = None
    image_model: Optional[str] = None
    mineru_api_base: Optional[str] = None
    mineru_token: Optional[str] = None
    image_caption_model: Optional[str] = None
    output_language: Optional[str] = None
    ai_provider_format: Optional[str] = None


class GeneratePageDescriptionRequest(BaseModel):
    force_regenerate: Optional[bool] = False
    language: Optional[str] = None


class GeneratePageImageRequest(BaseModel):
    use_template: Optional[bool] = True
    force_regenerate: Optional[bool] = False
    language: Optional[str] = None


class EditPageImageRequest(BaseModel):
    edit_instruction: str
    context_images: Optional[dict] = None
    use_template: Optional[bool] = False


class AssociateMaterialsRequest(BaseModel):
    project_id: str
    material_urls: list