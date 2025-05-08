import json
from pathlib import Path
from typing import Optional, Any, Dict, List

def save_file(content: str, filepath: Path, encoding: str = 'utf-8') -> None:
    """Save content to file with error handling."""
    try:
        with open(filepath, 'w', encoding=encoding) as f:
            f.write(content)
    except Exception as e:
        raise Exception(f"Error saving file {filepath}: {str(e)}")

def load_file(filepath: Path, encoding: str = 'utf-8') -> Optional[str]:
    """Load content from file with error handling."""
    try:
        with open(filepath, 'r', encoding=encoding) as f:
            return f.read()
    except Exception as e:
        raise Exception(f"Error loading file {filepath}: {str(e)}")

def save_conversation_history(history: List[Dict[str, Any]], filepath: Path) -> None:
    """Save conversation history to a JSON file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise Exception(f"Error saving conversation history: {str(e)}")

def load_conversation_history(filepath: Path) -> Optional[List[Dict[str, Any]]]:
    """Load conversation history from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise Exception(f"Error loading conversation history: {str(e)}")

def create_directories(directories: List[str]) -> None:
    """Create necessary directories if they don't exist."""
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True) 