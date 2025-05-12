import logging
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
    client = genai.Client(http_options=HttpOptions(api_version="v1"))
    google_search_tool = Tool(google_search=GoogleSearch())
    return client, google_search_tool

@retry_with_backoff(max_retries=3)
def table_of_contents_prompt(
    client: 'genai.Client',
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
    # Use provided config or fall back to default
    report_config = config or DEFAULT_REPORT_CONFIG
    
    # Determine the report type
    credit_card_product_type = report_config.get('credit_card_product_type', 'Premium Credit Cards')
    
    user_prompt = Part.from_text(text=f"""
        Create a professional **Table of Contents** in **{report_config['language']}** for an **executive-level strategic report** comparing **{credit_card_product_type}** products from **{report_config['primary_bank']}** and **{', '.join(report_config['comparison_banks'])}**. This TOC will serve as a **planner for a language model** to generate the full report, so clarity, logical flow, and completeness are essential.
        The report is for the **Executives of {report_config['primary_bank']}** and should follow a smooth, narrative-driven structure.

        **Report Structure:**
        {"Strict adherence to this section structure is required:" if config['strict_structure'] else "Use this table of contents as a **guideline**, but adjust it if necessary to support **clear analysis** and maintain logical flow."}
        {', '.join(config['report_sections'])}

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
    """)
    contents.append(Content(role="user", parts=[user_prompt]))
    response = client.models.generate_content(
        model=model_id,
        contents=contents,
        config=GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=65535,
            tools=[google_search_tool],
            response_modalities=["TEXT"],
            system_instruction=[Part.from_text(text=system_prompt)]
        )
    )
    text = response.text
    contents.append(Content(role="model", parts=[Part.from_text(text=text)]))
    logger.info("✅ Table of Contents generated successfully")
    log_to_request_file(request_id, "generating", "✅ Table of Contents generated successfully")
    return user_prompt, text, response

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
    logger.info("📋 Extracting main sections from Table of Contents...")
    log_to_request_file(request_id, "generating", "📋 Extracting main sections from Table of Contents...")
    
    # Use provided config or fall back to default
    report_config = config or DEFAULT_REPORT_CONFIG
    
    user_prompt = Part.from_text(text=f"""From the detailed Table of Contents in {report_config['language']} above, extract:
          1. The main report title (first line)
          2. All main sections marked with Roman numerals (e.g., I., II., III.)

          Return in this format:
          TITLE: [Report Title]
          SECTIONS:
          [Section 1]
          [Section 2]
          [Section 3]

          Do not add any introductory phrases or explanations to your response.""")
    
    response = client.models.generate_content(
        model=flash_model_id,
        contents=[
            Content(role="user", parts=[context_user_prompt]),
            Content(role="model", parts=[Part.from_text(text=context_text)]),
            Content(role="user", parts=[user_prompt])
        ],
        config=GenerateContentConfig(
            temperature=0,
            top_p=0.95,
            seed=0,
            safety_settings=report_config.get('safety_settings', None),
            response_modalities=["TEXT"],
            system_instruction=[Part.from_text(text=system_prompt)]
        )
    )
    text = response.text
    logger.info("✅ Sections extracted successfully")
    log_to_request_file(request_id, "generating", "✅ Sections extracted successfully")
    return user_prompt, text, response