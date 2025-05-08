import logging
import re
from google.genai.types import Part, Content, GenerateContentConfig
from config import REPORT_CONFIG
from utils import retry_with_backoff

logger = logging.getLogger(__name__)

@retry_with_backoff(max_retries=3)
def generate_section_content(client, model_id, section_title, section_number, contents, system_prompt, google_search_tool):
    """Generate content for a specific report section."""
    logger.info(f"📝 Generating content for section {section_number}: {section_title}")
    user_prompt = Part.from_text(text=f"""
            Based on the guidance in the table of contents section, connect with the previous section, write a comprehensive and professionally worded section of our strategic report on the section {section_title}. 
            The content should be tailored for Kookmin Bank's {REPORT_CONFIG['language']}-speaking executive audience, including the CFO and other C-level stakeholders.
            Even though the guidance is a very useful information to write the section, please do not include the guidance in the top of the section and sub-sections.

            CRITICAL LANGUAGE REQUIREMENTS:
            - Entire content must be in formal {REPORT_CONFIG['language']} with proper business terms
            - No other languages allowed
            - Use {REPORT_CONFIG['language']} format for numbers, dates, currency, and percentages
            - For bullet points, use hyphens (-) instead of asterisks (*) to ensure proper PDF rendering

            IMPORTANT: **Always combine with the provided Google Search tool** to gather the most recent, reliable, and relevant information on this section. 
            
            **Data Verification Requirements:**
            1. Include only well-confirmed information cross-verified by at least 2–3 reliable, recent sources; mark or omit anything unverified.
            2. Prioritize depth and accuracy over quantity—focus on thoroughly analyzing a few confirmed points rather than covering many uncertain ones.

            **Content Depth Requirements:**
            1. For each confirmed data point:
               - Provide detailed analysis
               - Include relevant context
               - Explain implications
               - Connect to broader market trends
            2. Use specific numbers and statistics when available
            3. Include direct quotes from reliable sources when relevant
            4. Analyze trends and patterns in the data
            5. Draw clear connections between different data points

            **Writing Style Requirements:**
            - Use a flowing, narrative style with smooth transitions and a professional, engaging tone
            - Build a compelling story with insights, data, and clear calls to action
            - Tailor content for a {REPORT_CONFIG['language']}-speaking audience, ensuring cultural and linguistic relevance

            **Data Presentation:**
            1. Use tables for structured data comparisons and detailed metrics
            2. Format tables using markdown table syntax:
            | Header 1 | Header 2 | Header 3 |
            |----------|----------|----------|
            | Data 1   | Data 2   | Data 3   |
            3. Include table captions or explanatory text before/after tables
            4. Use tables to present:
            - Financial metrics comparisons
            - Market share data
            - Feature comparisons
            - Performance metrics
            - Cost structures
            5. Ensure tables are properly integrated into the narrative flow

            **Formatting Guidelines:**
            1. Use proper markdown heading levels:
            - `##` for main sections
            - `###` for subsections
            - `####` for sub-subsections
            2. Add one blank line before and after each heading
            3. Format example: `## I. Section Title`

            **Writing Tips:**
            - Turn bullet points into clear, connected paragraphs using active voice and strong verbs
            - Support ideas with specific examples or data, and end with forward-looking statements

            **Quality Control:**
            1. Verify all claims with multiple sources
            2. Ensure all data is current and relevant
            3. Check for consistency across the report
            4. Validate all numerical information
            5. Confirm all quotes and citations

            Remember: It's better to have fewer, well-verified points than many uncertain ones. Focus on depth of analysis for confirmed information rather than trying to cover everything.
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
        logger.info(f"📚 Found {len(grounding_chunks)} grounding citations")
        sorted_supports = sorted(grounding_supports, key=lambda s: len(s.segment.text), reverse=True)
        for support in sorted_supports:
            segment_text = support.segment.text.strip()
            indices = support.grounding_chunk_indices or []
            if not indices:
                continue
            superscript_links = []
            for i in indices:
                try:
                    uri = grounding_chunks[i].web.uri if grounding_chunks[i].web else ""
                    ref_id = f"ref-{section_number}-{i+1}"
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
        logger.warning("⚠️ Agent decided not to use Google Search for this section")
    logger.info(f"✅ Content generated for section {section_number}")
    return text, report_references, response