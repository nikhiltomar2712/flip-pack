#!/usr/bin/env python3
"""
Metadata Editor - Edit EXIF, ID3, and other metadata tags
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any
import json

# For images
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# For audio
try:
    import mutagen
    from mutagen.easyid3 import EasyID3
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

class MetadataEditor:
    @staticmethod
    def get_file_type(file_path: Path) -> str:
        """Determine file type based on extension"""
        ext = file_path.suffix.lower()
        
        image_exts = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.webp'}
        audio_exts = {'.mp3', '.flac', '.m4a', '.ogg', '.wma'}
        
        if ext in image_exts:
            return 'image'
        elif ext in audio_exts:
            return 'audio'
        else:
            return 'unknown'
    
    def read_exif(self, file_path: str) -> Dict[str, Any]:
        """Read EXIF metadata from image"""
        if not PIL_AVAILABLE:
            raise ImportError("Pillow library required. Install with: pip install Pillow")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            img = Image.open(file_path)
            exif_data = img._getexif()
            
            if not exif_data:
                return {}
            
            exif_dict = {}
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                exif_dict[tag_name] = str(value)
            
            return exif_dict
        except Exception as e:
            raise RuntimeError(f"Failed to read EXIF: {e}")
    
    def write_exif(self, file_path: str, metadata: Dict[str, Any]):
        """Write EXIF metadata to image (limited support)"""
        if not PIL_AVAILABLE:
            raise ImportError("Pillow library required. Install with: pip install Pillow")
        
        # PIL doesn't support writing EXIF directly well
        # For full EXIF writing, consider using pyexiv2 or exiftool
        print("Warning: Full EXIF writing has limited support. Consider using exiftool.")
        
        file_path = Path(file_path)
        img = Image.open(file_path)
        
        # Basic metadata writing example
        if 'description' in metadata:
            img.info['description'] = metadata['description']
        
        # Save with new metadata (this is simplified)
        # img.save(file_path, exif=...)
    
    def read_id3(self, file_path: str) -> Dict[str, Any]:
        """Read ID3 tags from audio files"""
        if not MUTAGEN_AVAILABLE:
            raise ImportError("Mutagen library required. Install with: pip install mutagen")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            if file_path.suffix.lower() == '.mp3':
                audio = EasyID3(file_path)
            elif file_path.suffix.lower() == '.flac':
                audio = FLAC(file_path)
            else:
                audio = mutagen.File(file_path)
            
            if not audio:
                return {}
            
            # Extract common tags
            tags = {}
            for key in ['title', 'artist', 'album', 'date', 'genre', 'tracknumber']:
                if key in audio:
                    tags[key] = audio[key][0] if isinstance(audio[key], list) else audio[key]
            
            # Add technical info
            if hasattr(audio, 'info'):
                tags['length'] = audio.info.length
                tags['bitrate'] = getattr(audio.info, 'bitrate', None)
                tags['sample_rate'] = getattr(audio.info, 'sample_rate', None)
            
            return tags
        except Exception as e:
            raise RuntimeError(f"Failed to read ID3 tags: {e}")
    
    def write_id3(self, file_path: str, metadata: Dict[str, Any]):
        """Write ID3 tags to audio files"""
        if not MUTAGEN_AVAILABLE:
            raise ImportError("Mutagen library required. Install with: pip install mutagen")
        
        file_path = Path(file_path)
        
        try:
            if file_path.suffix.lower() == '.mp3':
                audio = EasyID3(file_path)
            elif file_path.suffix.lower() == '.flac':
                audio = FLAC(file_path)
            else:
                audio = mutagen.File(file_path)
            
            if not audio:
                raise ValueError(f"Cannot edit tags for {file_path}")
            
            # Write tags
            for key, value in metadata.items():
                if key in ['title', 'artist', 'album', 'date', 'genre', 'tracknumber']:
                    audio[key] = str(value)
            
            audio.save()
            print(f"✅ Updated tags for {file_path.name}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to write ID3 tags: {e}")
    
    def list_supported_formats(self) -> Dict[str, list]:
        """List supported file formats for metadata operations"""
        formats = {
            'image': ['jpg', 'jpeg', 'png', 'tiff', 'bmp', 'webp'] if PIL_AVAILABLE else [],
            'audio': ['mp3', 'flac', 'm4a', 'ogg'] if MUTAGEN_AVAILABLE else []
        }
        return formats

def main():
    parser = argparse.ArgumentParser(description="Edit file metadata (EXIF, ID3, etc.)")
    parser.add_argument('file', help='File to edit')
    parser.add_argument('--read', action='store_true', help='Read metadata')
    parser.add_argument('--write', help='Write metadata (JSON string or file)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    editor = MetadataEditor()
    file_path = Path(args.file)
    
    # Determine file type
    file_type = editor.get_file_type(file_path)
    
    if file_type == 'image':
        if args.read:
            try:
                exif = editor.read_exif(file_path)
                if args.json:
                    print(json.dumps(exif, indent=2))
                else:
                    for tag, value in exif.items():
                        print(f"{tag}: {value}")
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
        
        elif args.write:
            try:
                metadata = json.loads(args.write) if args.write.startswith('{') else json.load(open(args.write))
                editor.write_exif(file_path, metadata)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
    
    elif file_type == 'audio':
        if args.read:
            try:
                tags = editor.read_id3(file_path)
                if args.json:
                    print(json.dumps(tags, indent=2, default=str))
                else:
                    for tag, value in tags.items():
                        print(f"{tag}: {value}")
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
        
        elif args.write:
            try:
                metadata = json.loads(args.write) if args.write.startswith('{') else json.load(open(args.write))
                editor.write_id3(file_path, metadata)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
    
    else:
        print(f"Unsupported file type: {file_path.suffix}", file=sys.stderr)
        print(f"Supported formats: {editor.list_supported_formats()}", file=sys.stderr)

if __name__ == "__main__":
    main()
