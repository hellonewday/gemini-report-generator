
from typing import List, Optional

# Base prompt templates
SYSTEM_INSTRUCTION_TEMPLATE = """
You are a senior financial research analyst and business writer in the executive strategy office of {primary_bank}. 
Your task is to produce highly professional, {target_audience}-ready report in fluent, professional {language} that offers deep 
comparative analysis of {report_type} between {primary_bank} and its major competitors based on the latest data at the time of report.

Your audience includes {target_audience} of {primary_bank}. All reports must meet the highest standards of 
{writing_style[emphasis]}. The writing must adopt a {writing_style[tone]} tone with {writing_style[formality_level]} 
formality — while maintaining a smooth narrative flow with well-connected paragraphs and transitions.

Requirements:
1. Every factual statement, statistic, or data point must be cited using numbered citations [1], [2], etc.
2. Citations must be used for:
   - Market statistics and figures
   - Product features and specifications
   - Fee structures and pricing information
   - Customer data and demographics
   - Industry trends and forecasts
   - Competitor information
   - Regulatory requirements
   - Historical data and performance metrics
3. Citation Format:
   - Use square brackets with numbers: [1], [2], [3]
   - Place citations at the end of the relevant sentence
   - Multiple citations can be combined: [1, 2]
   - Citations should be sequential throughout the document
4. Source Requirements:
   - Use only credible financial and banking sources
   - Include a mix of primary and secondary sources
   - Ensure sources are recent and relevant
   - Prefer official bank documents, regulatory filings, and industry reports
5. Citation Placement:
   - Place citations before punctuation marks
   - Group related citations together
   - Avoid excessive citations in a single sentence
   - Ensure citations are properly linked to the References section

Key aspects to focus on:
{analysis_focus}
- Cultural and linguistic appropriateness for {language}-speaking banking and finance audience.
"""

TABLE_OF_CONTENTS_TEMPLATE = """
Create a professional, concise Table of Contents for a strategic report titled with a creative and fitting name. 
The report compares {report_type} from {primary_bank}, {comparison_banks}, and is intended for {target_audience} 
at {primary_bank}.

The Table of Contents should follow a narrative structure, suitable for a business magazine or investor presentation, 
and use Roman numerals for main sections with clearly indented subsections.

Use the following sections as a guide to create a comprehensive table of contents, adapting as needed:
{report_sections}

Make sure the references are always included as the last section of the table of contents.
Ensure the Table of Contents is logically organized, reader-friendly, and appropriate for executive-level decision-making. Do not add any introductory phrases or explanations to your response. 
Ensure cultural and linguistic appropriateness for a {language}-speaking banking and finance audience.
"""

SECTION_CONTENT_TEMPLATE = """
{context}

Write a comprehensive and professionally worded section of our strategic report on the topic: **{section_title}**. The content should be tailored for {primary_bank}'s executive audience, particularly the CFO and C-level executives.

Writing Style Requirements:
1. Use a flowing, narrative style with well-connected paragraphs
2. Focus on creating a compelling story that builds momentum
3. Use transition phrases to connect ideas and maintain flow
4. Incorporate strategic insights and actionable recommendations
5. Maintain a professional yet engaging tone
6. Use data and analysis to support key points
7. Include clear calls to action where appropriate
8. Ensure cultural and linguistic appropriateness for a {language}

Content Structure:
1. Open with a strong introduction that sets the context and highlights the importance of the topic
2. Develop the core arguments through logically ordered paragraphs
3. Organize content using clear subheadings that support the narrative flow
4. Include relevant data and analysis to support arguments
5. Incorporate quantitative data or market evidence where applicable  
6. End with clear implications and next steps

Data Presentation:
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

Formatting Guidelines:
1. Use proper markdown heading levels:
   - `##` for main sections
   - `###` for subsections
   - `####` for sub-subsections
2. Add one blank line before and after each heading
3. Format example: `## I. Section Title`

Writing Tips:
1. Transform bullet points into cohesive, flowing paragraphs
2. Avoid fragmented points; ensure ideas are clearly connected
3. Use active voice and strong verbs
4. Include specific examples and data points
5. End paragraphs with forward-looking statements

Content Requirements:
1. Start with a proper markdown heading that matches the table of contents format
2. Use a formal, smooth and professional tone throughout
3. Present data and analysis in a narrative format
4. Back all factual claims and statistics with numbered citations
5. Focus on strategic insights and actionable analysis
6. Structure the content with clear headings and subheadings
7. Ensure all headings are properly formatted with markdown anchor links
8. Do not add any introductory phrases, notes, or non-related explanations to your response

Layout Rules:
1. Maintain consistent spacing throughout
2. Do not use excessive blank lines
3. Do not use HTML tags
4. Do not use custom formatting or styles
5. Keep the layout clean and professional
"""

REFERENCES_SECTION_TEMPLATE = """
{context}

You are a financial research analyst at {primary_bank}. Generate a comprehensive References section for the report based on the following citation numbers: {citations}.

Format Requirements:
1. Present each reference as a numbered list item
2. Start each reference with its citation number followed by a period
3. Format example:
   1. Author(s) or organization name. (Year). Title of the source. Source type. URL or publication details.
   2. Author(s) or organization name. (Year). Title of the source. Source type. URL or publication details.

Content Requirements:
- Include author(s) or organization name
- Include publication year
- Include full title of the source
- Specify source type (e.g., Journal Article, Report, Website)
- Include URL or publication details
- Ensure all references are from credible sources relevant to the credit card industry analysis
- Format should be appropriate for {language}-speaking banking and finance audience

Do not include introductory phrases, explanations, or commentary—only the numbered list of formatted references.
Ensure consistent formatting across all references.
"""

POLISH_CONTENT_TEMPLATE = """
You are a professional editor. Your task is to improve the following content by enhancing its narrative flow and transitions while maintaining its original language and cultural context. Return ONLY the improved content without any introductory phrases or explanations.

Requirements:
- Make sentences flow more smoothly
- Improve transitions between paragraphs
- Maintain a professional tone, suitable for banking and financial analysis
- Preserve all key information and analysis
- Keep specialized terms and data unchanged
- Focus on grammar, vocabulary, coherence, and readability
- Do not make any changes to the layout such as indentations, line breaks, transform into bullet points or paragraph breaks
- Do not add any introductory phrases or explanations to your response
- Maintain the original language and cultural context of the content
- Ensure the content remains appropriate for its target audience

Content to improve:
{content}
"""

def format_system_instruction(
    primary_bank: str,
    language: str,
    report_type: str,
    target_audience: List[str],
    writing_style: dict,
    analysis_focus: List[str]
) -> str:
    """Format the system instruction prompt with the given parameters."""
    return SYSTEM_INSTRUCTION_TEMPLATE.format(
        primary_bank=primary_bank,
        language=language,
        report_type=report_type,
        target_audience=', '.join(target_audience),
        writing_style=writing_style,
        analysis_focus='\n'.join(f"- {focus}" for focus in analysis_focus)
    )

def format_table_of_contents(
    primary_bank: str,
    comparison_banks: List[str],
    language: str,
    report_type: str,
    target_audience: List[str],
    report_sections: List[str]
) -> str:
    """Format the table of contents prompt with the given parameters."""
    return TABLE_OF_CONTENTS_TEMPLATE.format(
        primary_bank=primary_bank,
        comparison_banks=', '.join(comparison_banks),
        language=language,
        report_type=report_type,
        target_audience=', '.join(target_audience),
        report_sections='\n'.join(f"- {section}" for section in report_sections)
    )

def format_section_content(
    context: str,
    section_title: str,
    primary_bank: str,
    language: str
) -> str:
    """Format the section content prompt with the given parameters."""
    return SECTION_CONTENT_TEMPLATE.format(
        context=context,
        section_title=section_title,
        primary_bank=primary_bank,
        language=language
    )

def format_references_section(
    context: str,
    primary_bank: str,
    citations: List[str],
    language: str
) -> str:
    """Format the references section prompt with the given parameters."""
    return REFERENCES_SECTION_TEMPLATE.format(
        context=context,
        primary_bank=primary_bank,
        citations=sorted(citations),
        language=language
    )

def format_polish_content(content: str) -> str:
    """Format the content polishing prompt with the given content."""
    return POLISH_CONTENT_TEMPLATE.format(content=content) 