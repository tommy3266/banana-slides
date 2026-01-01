"""
Gemini-3 Image Generator Script

This script provides functionality to generate images using the Gemini-3 model
and save them to the local file system.
"""
import os
import sys
from typing import Optional
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import the GenAI SDK
try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai package is not installed.")
    print("Please install it using: pip install google-genai")
    sys.exit(1)


class GeminiImageGenerator:
    """Image generator using Google's Gemini-3 model"""
    
    def __init__(self, api_key: str = None, api_base: str = None, model: str = "gemini-3-pro-image-preview"):
        """
        Initialize the Gemini image generator
        
        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY environment variable)
            api_base: API base URL (defaults to GOOGLE_API_BASE environment variable)
            model: Model name to use (defaults to gemini-3-pro-image-preview)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.api_base = api_base or os.getenv("GOOGLE_API_BASE")
        self.model = model
        
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable or pass as parameter.")
        
        # Configure the client
        http_options = types.HttpOptions(
            base_url=self.api_base,
            timeout=60000  # 60 seconds timeout
        ) if self.api_base else types.HttpOptions(timeout=60000)
        
        self.client = genai.Client(
            http_options=http_options,
            api_key=self.api_key
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
        Generate an image using the Gemini-3 model
        
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
            # Build contents list with prompt and reference images
            contents = []
            
            # Add reference image if provided
            if ref_image_path and os.path.exists(ref_image_path):
                ref_image = Image.open(ref_image_path)
                contents.append(ref_image)
            
            # Add text prompt
            contents.append(prompt)
            
            print(f"Generating image with prompt: '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'")
            print(f"Reference image: {ref_image_path if ref_image_path else 'None'}")
            print(f"Aspect ratio: {aspect_ratio}, Resolution: {resolution}")
            
            # Call the Gemini API
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                        image_size=resolution
                    ),
                )
            )
            
            # Extract image from response
            image_found = False
            for i, part in enumerate(response.parts):
                if part.text is not None:
                    print(f"API Response Text: {part.text}")
                else:
                    try:
                        image = part.as_image()
                        if image:
                            print(f"Successfully extracted image from response part {i}")
                            
                            # Save the image to the specified path
                            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
                            image.save(output_path)
                            print(f"Image saved successfully to: {output_path}")
                            image_found = True
                            
                            # Show image info
                            print(f"Generated image size: {image.size}")
                            break
                    except Exception as e:
                        print(f"Failed to extract image from part {i}: {str(e)}")
            
            if not image_found:
                print("No image found in API response")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error generating image: {type(e).__name__}: {str(e)}")
            return False


def main():
    """Main function to demonstrate the image generation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate images using Gemini-3 model")
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
        # Initialize the generator
        generator = GeminiImageGenerator()
        
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
        sys.exit(1)


if __name__ == "__main__":
    # python .\gemini_image_generator.py --prompt "生成一个小马"
    main()