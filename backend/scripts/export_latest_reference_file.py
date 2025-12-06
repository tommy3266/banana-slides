"""
Export the latest reference file's markdown content to a file
"""
import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from models import db, ReferenceFile

def export_latest_reference_file():
    """Export the latest reference file's markdown content"""
    app = create_app()
    
    with app.app_context():
        # Get the latest reference file
        latest_file = ReferenceFile.query.order_by(
            ReferenceFile.created_at.desc()
        ).first()
        
        if not latest_file:
            print("No reference files found in database.")
            return
        
        print(f"Found latest reference file:")
        print(f"  ID: {latest_file.id}")
        print(f"  Filename: {latest_file.filename}")
        print(f"  Status: {latest_file.parse_status}")
        print(f"  Created: {latest_file.created_at}")
        print(f"  Project ID: {latest_file.project_id}")
        
        if not latest_file.markdown_content:
            print("\nError: This file has no markdown content.")
            if latest_file.parse_status != 'completed':
                print(f"  Parse status: {latest_file.parse_status}")
                if latest_file.error_message:
                    print(f"  Error: {latest_file.error_message}")
            return
        
        # Create output directory
        output_dir = backend_dir / 'exports'
        output_dir.mkdir(exist_ok=True)
        
        # Generate output filename
        safe_filename = latest_file.filename.rsplit('.', 1)[0] if '.' in latest_file.filename else latest_file.filename
        # Remove invalid characters for filename
        safe_filename = "".join(c for c in safe_filename if c.isalnum() or c in (' ', '-', '_')).strip()
        output_file = output_dir / f"{safe_filename}_export.md"
        
        # Write markdown content to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(latest_file.markdown_content)
        
        print(f"\nMarkdown content exported to:")
        print(f"  {output_file}")
        print(f"  Content length: {len(latest_file.markdown_content)} characters")
        print(f"  First 500 characters:")
        print(f"  {'='*60}")
        print(f"  {latest_file.markdown_content[:500]}...")
        print(f"  {'='*60}")

if __name__ == '__main__':
    export_latest_reference_file()

