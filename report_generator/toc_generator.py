import logging
from typing import Tuple, List
from google.genai.types import Part, Content, GenerateContentConfig, Tool, GoogleSearch
from config import REPORT_CONFIG
from utils import retry_with_backoff

logger = logging.getLogger(__name__)

def setup_client_and_tools() -> Tuple['genai.Client', Tool]:
    """Set up the client and Google Search tool.

    Returns:
        Tuple[genai.Client, Tool]: The initialized client and Google Search tool.
    """
    from google import genai
    client = genai.Client(
        vertexai=True,
        project="nth-droplet-458903-p4",
        location="us-central1",
    )
    google_search_tool = Tool(google_search=GoogleSearch())
    return client, google_search_tool

@retry_with_backoff(max_retries=3)
def table_of_contents_prompt(
    client: 'genai.Client',
    model_id: str,
    contents: List[Content],
    system_prompt: str,
    google_search_tool: Tool
) -> Tuple[Part, str, 'GenerateContentResponse']:
    """Generate the Table of Contents for the report.

    Args:
        client: The genai client instance.
        model_id: The model ID to use for generation.
        contents: The list of conversation contents.
        system_prompt: The system prompt for the model.
        google_search_tool: The Google Search tool instance.

    Returns:
        Tuple[Part, str, GenerateContentResponse]: The user prompt, generated text, and response object.

    Raises:
        Exception: If content generation fails after retries.
    """
    logger.info("Generating Table of Contents...")
    user_prompt = Part.from_text(text=f"""
            Create a professional **Table of Contents** in **{REPORT_CONFIG['language']}** for an **executive-level strategic report** comparing **credit card products** from **KB Kookmin Bank**, **Hana SEB Bank**, and **Woori Bank**. This TOC will serve as a **planner for a language model** to generate the full report, so clarity, logical flow, and completeness are essential.
            The report is for the **Executives of KB Kookmin Bank** and should follow a smooth, narrative-driven structure.

            **Instructions:**

            * Write a **{REPORT_CONFIG['language']}-only** report title that is concise, aspirational, compelling, and relevant
            * All main sections marked with Roman numerals (e.g., I., II., III.)
            * All section and subsection **titles and guidance** must be written in **formal {REPORT_CONFIG['language']} business language**.
            * Each section/subsection must include a **brief description in {REPORT_CONFIG['language']}** explaining the content and purpose.
            * Ensure the tone is suitable for a **C-level financial audience**—clear, concise, and strategic.
            * Maintain cultural and linguistic appropriateness for a banking/finance readership.
            * Do not include References and Appendices section in this Table of Contents.
            * **IMPORTANT:** Do not use parentheses () in section titles. Instead, use colons : or dashes - to separate additional information.

            Do not make hypotheses or assumptions on what should be included in the report. 
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
    logger.info("Table of Contents generated successfully")
    return user_prompt, text, response

@retry_with_backoff(max_retries=3)
def extract_table_of_contents(
    client: 'genai.Client',
    flash_model_id: str,
    context_user_prompt: Part,
    context_text: str,
    system_prompt: str
) -> Tuple[Part, str, 'GenerateContentResponse']:
    """Extract main sections from the Table of Contents.

    Args:
        client: The genai client instance.
        flash_model_id: The flash model ID to use for extraction.
        context_user_prompt: The original TOC generation prompt.
        context_text: The generated TOC text.
        system_prompt: The system prompt for the model.

    Returns:
        Tuple[Part, str, GenerateContentResponse]: The user prompt, extracted text, and response object.

    Raises:
        Exception: If content extraction fails after retries.
    """
    logger.info("Extracting main sections from Table of Contents...")
    user_prompt = Part.from_text(text=f"""From the detailed Table of Contents in {REPORT_CONFIG['language']} above, extract:
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
            safety_settings=REPORT_CONFIG['safety_settings'],
            response_modalities=["TEXT"],
            system_instruction=[Part.from_text(text=system_prompt)]
        )
    )
    text = response.text
    logger.info("Sections extracted successfully")
    return user_prompt, text, response