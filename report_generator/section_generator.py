import logging
import re
from typing import Tuple, List, Dict, Any, Optional
from google.genai.types import Part, Content, GenerateContentConfig, Tool
from config import REPORT_CONFIG as DEFAULT_REPORT_CONFIG
from utils import retry_with_backoff, log_to_request_file

logger = logging.getLogger(__name__)

@retry_with_backoff(max_retries=3)
def generate_section_content(
    client: 'genai.Client',
    model_id: str,
    section_title: str,
    section_number: int,
    contents: List[Content],
    system_prompt: str,
    google_search_tool: 'Tool',
    request_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[str, List[str], 'GenerateContentResponse']:
    """Generate content for a specific report section.

    Args:
        client: The genai client instance.
        model_id: The model ID to use for generation.
        section_title: The title of the section.
        section_number: The section number (1-based).
        contents: The list of conversation contents.
        system_prompt: The system prompt for the model.
        google_search_tool: The Google Search tool instance.
        request_id: Optional request ID for logging.
        config: Optional configuration dictionary.

    Returns:
        Tuple[str, List[str], GenerateContentResponse]: The generated text, list of references, and response object.

    Raises:
        Exception: If content generation fails after retries.
    """
    logger.info(f"📝 Generating section {section_number}: {section_title}")
    
    # Use provided config or fall back to default
    report_config = config or DEFAULT_REPORT_CONFIG
    
    # Get key parameters from config
    primary_bank = report_config['primary_bank']
    
    user_prompt = Part.from_text(text=f"""
    You are a strategic report writer. Your task is to compose a comprehensive, professionally worded section of our strategic report titled **{section_title}**, intended for {primary_bank}'s {report_config['language']}-speaking executive audience, including the CFO and other C-level stakeholders.

    Use the guidance from the table of contents **only internally** to shape structure and coverage. **Do not include or reference** the guidance or section titles in the output.

    ---

    ## LANGUAGE & FORMATTING REQUIREMENTS

    - Write in **formal {report_config['language']}**, using correct business terminology.
    - **No other languages** are allowed.
    - Use correct {report_config['language']} formatting for:
    - Numbers
    - Dates
    - Currencies
    - Percentages
    - For bullet points, **use hyphens (-)** instead of asterisks (*) to ensure proper PDF rendering.
    - Use **Markdown heading levels** for structure:
    - `##` for main sections
    - `###` for subsections
    - `####` for sub-subsections
    - Add **one blank line** before and after each heading.
    - Example: `## I. Section Title`

    ---

    ## SECTION INTEGRITY RULE

    - **DO NOT** include any part of the guidance or TOC text in the section.
    - **DO NOT** summarize or repeat TOC items in the output.
    - Build the content as a **standalone section**, logically connected to the previous one.

    ---

    ## DATA VERIFICATION REQUIREMENTS

    Use the provided **Google Search tool** to obtain the most recent and reliable information.

    Only include information that:
    1. Has been **verified by at least 2–3 trustworthy, recent sources**.
    2. Is **current, credible, and relevant** to the section’s scope.

    If a point cannot be verified, either **omit it** or explicitly mark it as unverified.

    ---

    ## CONTENT DEPTH REQUIREMENTS

    For every confirmed data point:
    - Provide a **detailed analysis**
    - Include **market or industry context**
    - Explain **implications for {primary_bank}**
    - Connect to **broader macro or financial trends**

    Additionally:
    - Include **specific statistics or numbers** when available.
    - Integrate **relevant direct quotes** from reliable sources.
    - Analyze **trends, relationships, and patterns** in data.
    - Draw **insightful connections** across topics.

    ---

    ## WRITING STYLE REQUIREMENTS

    - Use a **flowing, narrative style** with smooth transitions.
    - Maintain a **professional, analytical, and engaging tone**.
    - Avoid dry enumeration—**build a compelling story**.
    - Ensure the writing is appropriate for a **{report_config['language']}-speaking, executive audience**.

    ---

    ## DATA PRESENTATION RULES

    When presenting data:
    - Use **tables** for structured comparisons.
    - Format using **markdown table syntax**:
    
    | Metric | Value | Comparison |
    |--------|-------|------------|
    | Example | 20% | +5pp YoY |

    - Add explanatory **captions or context** before/after tables.
    - Use tables for:
    - Financial or KPI comparisons
    - Market share breakdowns
    - Performance metrics
    - Cost structures
    - Feature or service comparisons

    Ensure each table integrates smoothly with surrounding analysis.

    ---

    ## WRITING TIPS

    - Turn bullet points into cohesive, analytical paragraphs.
    - Use **active voice** and strong verbs.
    - Support all points with **data, examples, or source citations**.
    - End with **forward-looking insights** or recommendations when relevant.

    ---

    ## QUALITY CONTROL CHECKLIST

    Before finalizing, ensure that:
    - All data is verified and up to date.
    - All numbers, statistics, and quotes are accurate.
    - The section is internally consistent and coherent.
    - All formatting and style guidelines are followed.

    ---

    ## FINAL REMINDER

    - **Do not include any TOC or guidance text.**
    - **Use only verified data and current sources.**
    - **Return only the final formatted report section.**
    - **No explanations, commentary, or notes.**
    """)

    contents.append(Content(role="user", parts=[user_prompt]))
    response = client.models.generate_content(
        model=model_id,
        contents=contents,
        config=GenerateContentConfig(
            tools=[google_search_tool],
            temperature=0,
            max_output_tokens=65535,
            response_modalities=["TEXT"],
            system_instruction=[Part.from_text(text=system_prompt)]
        )
    )
    text = response.text
    contents.append(Content(role="model", parts=[Part.from_text(text=text)]))

    # Handle grounding metadata for references
    report_references = []
    grounding_metadata = response.candidates[0].grounding_metadata
    grounding_chunks = None if grounding_metadata is None else grounding_metadata.grounding_chunks
    grounding_supports = None if grounding_metadata is None else grounding_metadata.grounding_supports
    if grounding_supports and grounding_chunks:
        logger.info(f"Found {len(grounding_chunks)} grounding citations")
        sorted_supports = sorted(grounding_supports, key=lambda s: len(s.segment.text), reverse=True)
        for support in sorted_supports:
            segment_text = support.segment.text.strip()
            indices = support.grounding_chunk_indices or []
            if not indices:
                continue
            superscript_links = []
            for i in indices:
                try:
                    superscript_links.append(f'<sup><a href="#ref-section-{section_number}-{i+1}">[{section_number}.{i+1}]</a></sup>')
                except (IndexError, AttributeError):
                    continue
            if not superscript_links:
                continue
            superscript = "".join(superscript_links)
            replacement = f"{segment_text}{superscript}"
            pattern = re.escape(segment_text)
            text = re.sub(pattern, replacement, text, count=1)

        section_references = f"\n\n#### {section_title} \n\n<div class='references-grid'>\n"
        for idx, chunk in enumerate(grounding_chunks):
            web = chunk.web
            if web:
                section_references += f'<div class="reference-item" id="ref-section-{section_number}-{idx+1}">{idx+1}. <a href="{web.uri}">{web.domain}</a></div>\n'
            else:
                section_references += f'<div class="reference-item" id="ref-section-{section_number}-{idx+1}">{idx+1}. No web metadata available.</div>\n'
        section_references += '</div>\n---\n\n'
        report_references.append(section_references)
    else:
        logger.warning("Agent decided not to use Google Search for this section")
    
    logger.info(f"✅ Section {section_number} content generated successfully")
    log_to_request_file(request_id, "generating", f"✅ Section {section_number} content generated successfully")
    return text, report_references, response