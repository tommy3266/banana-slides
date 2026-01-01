"""
Example usage of the Gemini Image Generator

This script demonstrates how to use the image generators with example prompts.
"""
import os
from pathlib import Path

def main():
    """Example usage of the Gemini image generators"""
    print("=== Gemini Image Generator Examples ===\n")
    
    # Example prompts
    example_prompts = [
        "A beautiful landscape with mountains and a lake at sunset",
        "A futuristic city with flying cars and skyscrapers",
        "A cute cat sitting on a windowsill with plants around",
        "A professional business presentation slide with charts",
        "An abstract art piece with vibrant colors and geometric shapes"
    ]
    
    print("Available generators:")
    print("1. Basic Generator (gemini_image_generator.py)")
    print("2. Advanced Generator (gemini_image_gen_advanced.py) - uses project's implementation\n")
    
    print("Example usage commands:\n")
    
    # Show example commands for basic generator
    print("# Using the basic generator:")
    for i, prompt in enumerate(example_prompts[:2], 1):
        output_path = f"output/example_basic_{i}.png"
        cmd = f"python gemini_image_generator.py --prompt \"{prompt}\" --output \"{output_path}\""
        print(f"  {cmd}")
    print()
    
    # Show example commands for advanced generator
    print("# Using the advanced generator:")
    for i, prompt in enumerate(example_prompts[:2], 1):
        output_path = f"output/example_advanced_{i}.png"
        cmd = f"python gemini_image_gen_advanced.py --prompt \"{prompt}\" --output \"{output_path}\""
        print(f"  {cmd}")
    print()
    
    print("Requirements:")
    print("- Set GOOGLE_API_KEY environment variable with your Gemini API key")
    print("- Install required packages: pip install google-genai pillow python-dotenv")
    print("- Optionally set GOOGLE_API_BASE for API proxy/custom endpoint")
    print()
    
    print("Configuration environment variables:")
    print("  GOOGLE_API_KEY=your_api_key_here           # Required")
    print("  GOOGLE_API_BASE=https://your-proxy.com     # Optional")
    print("  IMAGE_MODEL=gemini-3-pro-image-preview     # Optional, default from config")
    print()
    
    print("To run a quick test:")
    print("  1. Set your API key: export GOOGLE_API_KEY='your-key-here'")
    print("  2. Create output directory: mkdir -p output")
    print("  3. Run: python gemini_image_gen_advanced.py --prompt \"A beautiful sunset over the ocean\" --output \"output/sunset.png\"")


if __name__ == "__main__":
    main()