import logging
from typing import Tuple, Dict, Any, Optional
from google.genai.types import Part, Content, GenerateContentConfig
from config import REPORT_CONFIG as DEFAULT_REPORT_CONFIG
from utils import retry_with_backoff, log_to_request_file

logger = logging.getLogger(__name__)

@retry_with_backoff(max_retries=3)
def polish_content(
    client: 'genai.Client',
    flash_model_id: str,
    content: str,
    system_prompt: str,
    request_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[str, 'GenerateContentResponse']:
    """Polish content for better flow and readability.

    Args:
        client: The genai client instance.
        flash_model_id: The flash model ID to use for polishing.
        content: The content to polish.
        system_prompt: The system prompt for the model.
        request_id: Optional request ID for logging.
        config: Optional configuration dictionary.

    Returns:
        Tuple[str, GenerateContentResponse]: The polished text and response object.

    Raises:
        Exception: If content polishing fails after retries.
    """
    logger.info("✨ Polishing content...")
    log_to_request_file(request_id, "polishing", "✨ Polishing content...")
    
    # Use provided config or fall back to default
    report_config = config or DEFAULT_REPORT_CONFIG
    
    # Build localization section separately
    language = report_config['language']
    localization_section = ""

    if language.lower() != 'english':
        localization_section = f"""
    ### LANGUAGE & LOCALIZATION REQUIREMENTS:
    - Eliminate any translated-sounding or awkward phrasing
    - Remove hybrid expressions or unnatural literal translations
    - Make all wording feel native and idiomatic to a {language}-speaking C-level audience
    - Ensure culturally appropriate tone and vocabulary for business contexts
    """

    # Then compose the full user prompt
    user_prompt = Part.from_text(text=f"""
    You are a professional {language} editor with strong business writing experience. Improve the content's narrative flow and transitions while preserving its language, tone, and cultural context. Return only the revised text—no introductions, explanations, or additional information.

    Requirements:
    - Improve sentence flow, paragraph transitions, and overall readability
    - Maintain a professional tone for banking and financial analysis
    - Preserve all key content, analysis, terms, data, and cultural context
    - Do not alter layout (indentation, line breaks, bulleting, paragraphing)
    - Do not add introductions, explanations, descriptions or additional information. If the content is already well written, just return it as is.
    - Do not add any commentary or notes about the changes made
    - Keep superscript references and all HTML tags intact
    - Ensure suitability for a {language}-speaking audience
    - Maintain the original language and cultural context of the content
    - Keep all HTML tags intact, especially those related to references

    {localization_section}

    CRITICAL: 
    - Preserve ALL superscript references (e.g., <sup><a href="#ref-section-1-1">[1.1]</a></sup>) exactly as they appear, including their HTML tags and exact placement in the text
    - Return ONLY the polished content without any additional commentary or explanations
    - Do not add any notes about what was changed or improved

    Content to improve:
    {content}
    """)

        
    response = client.models.generate_content(
        model=flash_model_id,
        contents=[Content(role="user", parts=[user_prompt])],
        config=GenerateContentConfig(
            temperature=0.7,
            response_modalities=["TEXT"],
            safety_settings=report_config.get('safety_settings', None),
            system_instruction=system_prompt
        )
    )
    text = response.text
    logger.info("✅ Content polished successfully")
    log_to_request_file(request_id, "polishing", "✅ Content polished successfully")
    return text, response