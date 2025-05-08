import logging
from typing import Tuple
from google.genai.types import Part, Content, GenerateContentConfig
from config import REPORT_CONFIG
from utils import retry_with_backoff

logger = logging.getLogger(__name__)

@retry_with_backoff(max_retries=3)
def polish_content(
    client: 'genai.Client',
    flash_model_id: str,
    content: str,
    system_prompt: str
) -> Tuple[str, 'GenerateContentResponse']:
    """Polish content for better flow and readability.

    Args:
        client: The genai client instance.
        flash_model_id: The flash model ID to use for polishing.
        content: The content to polish.
        system_prompt: The system prompt for the model.

    Returns:
        Tuple[str, GenerateContentResponse]: The polished text and response object.

    Raises:
        Exception: If content polishing fails after retries.
    """
    logger.info("Polishing content for better flow and readability...")
    user_prompt = Part.from_text(text=f"""
      You are a professional {REPORT_CONFIG['language']} editor with strong business writing experience. Improve the content's narrative flow and transitions while preserving its language, tone, and cultural context. Return only the revised text—no introductions, explanations, or additional information.

      Requirements:
      - Improve sentence flow, paragraph transitions, and overall readability
      - Maintain a professional tone for banking and financial analysis
      - Preserve all key content, analysis, terms, data, and cultural context
      - Do not alter layout (indentation, line breaks, bulleting, paragraphing)
      - Do not add introductions, explanations, or additional information
      - Do not add any commentary or notes about the changes made
      - Keep superscript references and all HTML tags intact
      - Ensure suitability for a {REPORT_CONFIG['language']}-speaking audience
      - Maintain the original language and cultural context of the content
      - Ensure the content remains appropriate for {REPORT_CONFIG['language']}-speaking audience
      - Keep all HTML tags intact, especially those related to references

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
            safety_settings=REPORT_CONFIG['safety_settings'],
            system_instruction=[Part.from_text(text=system_prompt)]
        )
    )
    text = response.text
    logger.info("Content polished successfully")
    return text, response