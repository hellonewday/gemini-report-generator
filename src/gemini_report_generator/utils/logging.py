import logging
import os
from typing import Dict

def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """Setup logging configuration with emoji support."""
    # Define platform-specific emoji replacements
    emoji_map: Dict[str, str] = {
        '📝': '[START]',
        '📋': '[TOC]',
        '🔍': '[ANALYZE]',
        '📚': '[TITLE]',
        '📑': '[SECTIONS]',
        '📊': '[GENERATE]',
        '✨': '[POLISH]',
        '⏭️': '[SKIP]',
        '✅': '[SUCCESS]',
        '❌': '[ERROR]',
        '⏳': '[WAIT]',
        '🎉': '[COMPLETE]',
        '📄': '[FILE]',
        '🌐': '[HTML]',
        '📑': '[PDF]',
        '🌐': '[LANG]'
    }

    # Create a custom formatter that replaces emojis on Windows
    class EmojiSafeFormatter(logging.Formatter):
        def format(self, record):
            if os.name == 'nt':  # Windows
                msg = record.msg
                for emoji, text in emoji_map.items():
                    msg = msg.replace(emoji, text)
                record.msg = msg
            return super().format(record)

    # Setup logging with the custom formatter
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('report_generator.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Apply the custom formatter to all handlers
    formatter = EmojiSafeFormatter('%(asctime)s - %(levelname)s - %(message)s')
    for handler in logging.getLogger().handlers:
        handler.setFormatter(formatter)
        
    return logging.getLogger(__name__) 