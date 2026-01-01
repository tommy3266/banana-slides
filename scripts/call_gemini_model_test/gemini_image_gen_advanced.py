"""
Advanced Gemini Image Generator Script

This script uses the same implementation as the backend service to generate images 
using the Gemini-3 model and save them to the local file system.
"""
import os
import sys
from pathlib import Path
from typing import Optional, List
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to the Python path so we can import the project's modules
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

# Try to import the required packages
try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai package is not installed.")
    print("Please install it using: pip install google-genai")
    sys.exit(1)

# Import the configuration and image provider from the project
try:
    from config import get_config
    from services.ai_providers.image.genai_provider import GenAIImageProvider
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Make sure you're running this from the project root directory.")
    sys.exit(1)


class AdvancedGeminiImageGenerator:
    """Advanced image generator using the project's implementation"""
    
    def __init__(self):
        """Initialize the generator using project configuration"""
        config = get_config()
        
        # Get API key from environment or config
        api_key = config.GOOGLE_API_KEY
        if not api_key:
            raise ValueError(
                "Google API key is required. Set GOOGLE_API_KEY environment variable. "
                "Check backend/config.py for more details."
            )
        
        # Initialize the image provider using the same implementation as the backend
        self.provider = GenAIImageProvider(
            api_key=api_key,
            api_base=config.GOOGLE_API_BASE or None,
            model=config.IMAGE_MODEL,  # Uses IMAGE_MODEL from config (default: gemini-3-pro-image-preview)
            vertexai=False,  # Using AI Studio mode, not Vertex AI
            project_id=None,
            location=None
        )
    
    def generate_image(
        self,
        prompt: str,
        ref_image_path: Optional[str] = None,
        aspect_ratio: str = "16:9",
        resolution: str = "2K",
        output_path: str = "generated_image.png"
    ) -> bool:
        """
        Generate an image using the Gemini-3 model with project's implementation
        
        Args:
            prompt: The text prompt for image generation
            ref_image_path: Optional path to a reference image
            aspect_ratio: Image aspect ratio (default: "16:9")
            resolution: Image resolution (default: "2K", supports "1K", "2K", "4K")
            output_path: Path where the generated image will be saved
            
        Returns:
            True if image was generated and saved successfully, False otherwise
        """
        try:
            # Load reference image if provided
            ref_images = None
            if ref_image_path and os.path.exists(ref_image_path):
                ref_img = Image.open(ref_image_path)
                ref_images = [ref_img]
                print(f"Using reference image: {ref_image_path}")
            
            print(f"Generating image with prompt: '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'")
            print(f"Aspect ratio: {aspect_ratio}, Resolution: {resolution}")
            
            # Use the project's implementation to generate the image
            generated_image = self.provider.generate_image(
                prompt=prompt,
                ref_images=ref_images,
                aspect_ratio=aspect_ratio,
                resolution=resolution
            )
            
            if generated_image is None:
                print("Failed to generate image - no image returned from provider")
                return False
            
            # Save the image to the specified path
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
            generated_image.save(output_path)
            print(f"Image saved successfully to: {output_path}")
            print(f"Generated image size: {generated_image.size}")
            
            return True
            
        except Exception as e:
            print(f"Error generating image: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main function to demonstrate the advanced image generation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate images using Gemini-3 model (Advanced)")
    parser.add_argument("--prompt", type=str, required=True, help="Prompt for image generation")
    parser.add_argument("--ref-image", type=str, help="Path to reference image (optional)")
    parser.add_argument("--aspect-ratio", type=str, default="16:9", 
                       choices=["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
                       help="Aspect ratio for the generated image")
    parser.add_argument("--resolution", type=str, default="2K", 
                       choices=["1K", "2K", "4K"],
                       help="Resolution for the generated image")
    parser.add_argument("--output", type=str, default="output/generated_image.png",
                       help="Output path for the generated image")
    
    args = parser.parse_args()
    
    try:
        # Initialize the advanced generator
        generator = AdvancedGeminiImageGenerator()
        
        # Generate the image
        success = generator.generate_image(
            prompt=args.prompt,
            ref_image_path=args.ref_image,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
            output_path=args.output
        )
        
        if success:
            print("\n✅ Image generation completed successfully!")
        else:
            print("\n❌ Image generation failed!")
            sys.exit(1)
            
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()