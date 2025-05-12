import logging
import traceback
import sys
from typing import Tuple, List, Dict, Any, Optional
from google.genai.types import Part, Content, GenerateContentConfig, Tool, GoogleSearch, HttpOptions
from config import REPORT_CONFIG as DEFAULT_REPORT_CONFIG
from utils import retry_with_backoff, log_to_request_file
from google import genai

logger = logging.getLogger(__name__)

def setup_client_and_tools() -> Tuple['genai.Client', Tool]:
    """Set up the client and Google Search tool.

    Returns:
        Tuple[genai.Client, Tool]: The initialized client and Google Search tool.
    """
    client = genai.Client(
        vertexai=True,
        project="nth-droplet-458903-p4",
        location="us-central1",
    )
    google_search_tool = Tool(google_search=GoogleSearch())
    return client, google_search_tool


@retry_with_backoff(max_retries=3)
def table_of_contents_prompt(
    client,
    model_id: str,
    contents: List[Content],
    system_prompt: str,
    google_search_tool: Tool,
    request_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[Part, str, 'GenerateContentResponse']:
    """Generate the Table of Contents for the report.

    Args:
        client: The genai client instance.
        model_id: The model ID to use for generation.
        contents: The list of conversation contents.
        system_prompt: The system prompt for the model.
        google_search_tool: The Google Search tool instance.
        request_id: Optional request ID for logging.
        config: Optional configuration dictionary.

    Returns:
        Tuple[Part, str, GenerateContentResponse]: The user prompt, generated text, and response object.

    Raises:
        Exception: If content generation fails after retries.
    """    
    try:
        logger.info(f"📝 Generating Table of Contents with model: {model_id}")
        log_to_request_file(request_id, "generating", f"📝 Generating Table of Contents with model: {model_id}")
        
        # Use provided config or fall back to default
        report_config = config or DEFAULT_REPORT_CONFIG
        
        # Validate critical config parameters
        if not isinstance(report_config, dict):
            error_msg = f"❌ Invalid config type: {type(report_config).__name__}, expected dict"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise TypeError(error_msg)
            
        required_keys = ['language', 'primary_bank', 'comparison_banks', 'report_sections']
        for key in required_keys:
            if key not in report_config:
                error_msg = f"❌ Missing required config key: {key}"
                logger.error(error_msg)
                log_to_request_file(request_id, "error", error_msg)
                raise KeyError(error_msg)
        
        # Determine the report type with error handling
        try:
            credit_card_product_type = report_config.get('credit_card_product_type', 'Premium Credit Cards')
            logger.debug(f"Using credit card product type: {credit_card_product_type}")
        except Exception as e:
            error_msg = f"❌ Error getting credit card product type: {str(e)}"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            credit_card_product_type = "Premium Credit Cards"  # Fallback
            
        # Create user prompt with error handling
        try:
            user_prompt_text = f"""
                Create a professional **Table of Contents** in **{report_config['language']}** for an **executive-level strategic report** comparing **{credit_card_product_type}** products from **{report_config['primary_bank']}** and **{', '.join(report_config['comparison_banks'])}**. This TOC will serve as a **planner for a language model** to generate the full report, so clarity, logical flow, and completeness are essential.
                The report is for the **Executives of {report_config['primary_bank']}** and should follow a smooth, narrative-driven structure.

                **Report Structure:**
                {"Strict adherence to this section structure is required:" if report_config.get('strict_structure', False) else "Use this table of contents as a **guideline**, but adjust it if necessary to support **clear analysis** and maintain logical flow."}
                {', '.join(report_config['report_sections'])}

                **Instructions:**

                * Write a **concise and impactful** report title in **{report_config['language']}** that reflects the **comparative analysis of credit card products** and speaks to the strategic interests of **{report_config['primary_bank']}** executives.
                * All main sections marked with Roman numerals (e.g., I., II., III.), and use **colons** or **dashes** to separate sub-sections, **never parentheses**.
                * All section and subsection **titles and guidance** must be written in **formal {report_config['language']} business language**.
                * Each section and subsection must have a **concise description** in **{report_config['language']}**, outlining its purpose and guiding the content generation.
                * Ensure the tone is suitable for a **C-level financial audience**, emphasizing actionable insights and local market relevance. The focus should be on **strategic financial decision-making** and **product differentiation**.
                * Maintain cultural and linguistic appropriateness for a banking/finance readership.
                * Do not include **References** and **Appendices** section in this Table of Contents.
                * **IMPORTANT:** Do not use parentheses () in section titles. Instead, use **colons** or **dashes** to separate additional information.
                * Ensure **all sections** are **directly relevant** to the **local market** and **banking executives' decision-making**.

                **IMPORTANT:** Use the **Google Search tool** to gather the most recent and relevant information to ensure the TOC supports accurate and updated content generation.
            """
            user_prompt = Part.from_text(text=user_prompt_text)
            logger.debug("User prompt created successfully")
        except Exception as e:
            error_msg = f"❌ Error creating user prompt: {str(e)}"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise
            
        # Add prompt to contents
        try:
            contents.append(Content(role="user", parts=[user_prompt]))
            logger.debug("Added user prompt to contents")
        except Exception as e:
            error_msg = f"❌ Error adding user prompt to contents: {str(e)}"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise
            
        # Generate content with detailed error handling
        try:
            logger.info(f"Generating content with {model_id}...")
            log_to_request_file(request_id, "generating", f"Generating content with {model_id}...")
            
            # Prepare config
            generate_config = GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=65535,
                tools=[google_search_tool],
                response_modalities=["TEXT"],
                system_instruction=system_prompt
            )
            
            # # log the contents
            # vertex_client = genai.Client(
            #     vertexai=True,
            #     project="nth-droplet-458903-p4",
            #     location="us-central1",
            # )
            # Call API
            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=generate_config
            )
            
            logger.info("Content generation API call successful")
        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            error_msg = f"❌ Error generating content: {error_details}"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise
            
        # Extract text from response with error handling
        try:
            text = response.text
            if not text:
                error_msg = "❌ Empty response text from model"
                logger.error(error_msg)
                log_to_request_file(request_id, "error", error_msg)
                raise ValueError(error_msg)
            logger.debug(f"Successfully extracted text from response (length: {len(text)})")
        except Exception as e:
            if not hasattr(response, 'text'):
                error_msg = f"❌ Response object has no 'text' attribute: {response}"
                logger.error(error_msg)
                log_to_request_file(request_id, "error", error_msg)
            else:
                error_msg = f"❌ Error extracting text from response: {str(e)}"
                logger.error(error_msg)
                log_to_request_file(request_id, "error", error_msg)
            raise
            
        # Update contents with model response
        try:
            contents.append(Content(role="model", parts=[Part.from_text(text=text)]))
            logger.debug("Added model response to contents")
        except Exception as e:
            error_msg = f"❌ Error adding model response to contents: {str(e)}"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise
            
        logger.info("✅ Table of Contents generated successfully")
        log_to_request_file(request_id, "generating", "✅ Table of Contents generated successfully")
        return user_prompt, text, response
        
    except Exception as e:
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        error_msg = f"❌ Critical error in table_of_contents_prompt: {error_details}"
        logger.error(error_msg)
        log_to_request_file(request_id, "error", error_msg)
        raise

@retry_with_backoff(max_retries=3)
def extract_table_of_contents(
    client: 'genai.Client',
    flash_model_id: str,
    context_user_prompt: Part,
    context_text: str,
    system_prompt: str,
    request_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[Part, str, 'GenerateContentResponse']:
    """Extract main sections from the Table of Contents.

    Args:
        client: The genai client instance.
        flash_model_id: The flash model ID to use for extraction.
        context_user_prompt: The original TOC generation prompt.
        context_text: The generated TOC text.
        system_prompt: The system prompt for the model.
        request_id: Optional request ID for logging.
        config: Optional configuration dictionary.

    Returns:
        Tuple[Part, str, GenerateContentResponse]: The user prompt, extracted text, and response object.

    Raises:
        Exception: If content extraction fails after retries.
    """
    try:
        logger.info("📋 Extracting main sections from Table of Contents...")
        log_to_request_file(request_id, "generating", "📋 Extracting main sections from Table of Contents...")
        
        # Use provided config or fall back to default
        report_config = config or DEFAULT_REPORT_CONFIG
        
        # Validate inputs
        if not isinstance(context_user_prompt, Part):
            error_msg = f"❌ Invalid context_user_prompt type: {type(context_user_prompt).__name__}, expected Part"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise TypeError(error_msg)
            
        if not isinstance(context_text, str) or not context_text.strip():
            error_msg = f"❌ Invalid context_text: {'empty' if not context_text.strip() else type(context_text).__name__}"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise ValueError(error_msg)
            
        # Create extraction prompt
        try:
            user_prompt_text = f"""From the detailed Table of Contents in {report_config['language']} above, extract:
                  1. The main report title (first line)
                  2. All main sections marked with Roman numerals (e.g., I., II., III.)

                  Return in this format:
                  TITLE: [Report Title]
                  SECTIONS:
                  [Section 1]
                  [Section 2]
                  [Section 3]

                  Do not add any introductory phrases or explanations to your response."""
            user_prompt = Part.from_text(text=user_prompt_text)
            logger.debug("Extraction prompt created successfully")
        except Exception as e:
            error_msg = f"❌ Error creating extraction prompt: {str(e)}"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise
            
        # Create contents array for extraction
        try:
            extraction_contents = [
                Content(role="user", parts=[context_user_prompt]),
                Content(role="model", parts=[Part.from_text(text=context_text)]),
                Content(role="user", parts=[user_prompt])
            ]
            logger.debug("Created contents array for extraction")
        except Exception as e:
            error_msg = f"❌ Error creating contents array for extraction: {str(e)}"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise
            
        # Set up generate config for extraction
        try:
            extraction_config = GenerateContentConfig(
                temperature=0,
                top_p=0.95,
                seed=0,
                safety_settings=report_config.get('safety_settings', None),
                response_modalities=["TEXT"],
                system_instruction=system_prompt
            )
            logger.debug("Created extraction configuration")
        except Exception as e:
            error_msg = f"❌ Error creating extraction configuration: {str(e)}"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise
            
        # Generate content for extraction
        try:
            logger.info(f"Extracting TOC with model: {flash_model_id}")
            log_to_request_file(request_id, "generating", f"Extracting TOC with model: {flash_model_id}")
            
            response = client.models.generate_content(
                model=flash_model_id,
                contents=extraction_contents,
                config=extraction_config
            )
            
            logger.info("TOC extraction API call successful")
        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            error_msg = f"❌ Error in TOC extraction API call: {error_details}"
            logger.error(error_msg)
            log_to_request_file(request_id, "error", error_msg)
            raise
            
        # Extract text from extraction response
        try:
            text = response.text
            if not text:
                error_msg = "❌ Empty extraction response text"
                logger.error(error_msg)
                log_to_request_file(request_id, "error", error_msg)
                raise ValueError(error_msg)
            
            # Verify extraction format
            if not ("TITLE:" in text and "SECTIONS:" in text):
                warning_msg = "⚠️ Extraction response may not be in the expected format"
                logger.warning(warning_msg)
                log_to_request_file(request_id, "warning", warning_msg)
                
            logger.debug(f"Successfully extracted TOC text (length: {len(text)})")
        except Exception as e:
            if not hasattr(response, 'text'):
                error_msg = f"❌ Extraction response object has no 'text' attribute: {response}"
                logger.error(error_msg)
                log_to_request_file(request_id, "error", error_msg)
            else:
                error_msg = f"❌ Error extracting text from extraction response: {str(e)}"
                logger.error(error_msg)
                log_to_request_file(request_id, "error", error_msg)
            raise
            
        logger.info("✅ Sections extracted successfully")
        log_to_request_file(request_id, "generating", "✅ Sections extracted successfully")
        return user_prompt, text, response
        
    except Exception as e:
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
            "python_version": sys.version,
            "request_id": request_id
        }
        error_msg = f"❌ Critical error in extract_table_of_contents: {error_details}"
        logger.error(error_msg)
        log_to_request_file(request_id, "error", error_msg)
        raise