from google import genai
import markdown
import pdfkit
import re
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Part, Content, SafetySetting
from markdown.extensions.toc import TocExtension
import logging
import time
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

client = genai.Client(
            vertexai=True,
            project="nth-droplet-458903-p4",
            location="us-central1",
        )
model_id = "gemini-2.5-pro-preview-05-06"

google_search_tool = Tool(
      google_search = GoogleSearch()
)


system_prompt = """
You are a senior Korean financial analyst with 20 years of experience in the credit card market at Kookmin Bank. Your expertise spans banking regulations, market trends, and consumer behavior.

**CRITICAL REQUIREMENTS:**

1. LANGUAGE:
   - ALL content MUST be in Korean with no explaination in other languages
   - Use formal Korean business language
   - Format numbers, dates, currency, and percentages in Korean style

2. RESEARCH:
   - MUST use Google Search for EVERY section
   - Verify all information with multiple sources
   - Focus on financial news and official announcements
   - Ensure data is current and accurate

3. CONTENT QUALITY:
   - Executive-level, magazine-style presentation
   - Data-driven analysis with strategic insights
   - Clear narrative flow from macro to micro
   - Actionable recommendations
   - Culturally appropriate for banking context

4. STRUCTURE:
   - Professional table of contents
   - Logical section progression
   - Clear section descriptions
   - Proper formatting and organization
   - Please do not include References section in the report

5. WRITING STYLE:
   - Formal Korean business tone
   - Clear and concise language
   - Professional terminology
   - Proper data presentation
   - Strategic focus

**FINAL REMINDER:**
You MUST use Google Search for EVERY main section and ensure ALL content is in Korean. This is critical for the report's accuracy and value to Korean-speaking executives.
"""

contents=[]
report_references = []

def retry_with_backoff(max_retries=3, initial_delay=1, max_delay=10):
    """Decorator for retrying functions with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay = min(delay * 2, max_delay)
                    else:
                        logger.error(f"All {max_retries} attempts failed. Last error: {str(e)}")
                        raise last_exception
            
            return None
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3)
def table_of_contents_prompt():
    logger.info("🔄 Generating Table of Contents...")
    user_prompt = Part.from_text(text=f"""
            Create a professional **Table of Contents** in **Korean** for an **executive-level strategic report** comparing **credit card products** from **KB Kookmin Bank**, **Hana SEB Bank**, and **Woori Bank**. This TOC will serve as a **planner for a language model** to generate the full report, so clarity, logical flow, and completeness are essential.
            The report is for the **Excecutives of KB Kookmin Bank** and should follow a smooth, narrative-driven structure.

            **Instructions:**

            * Write a **Korean-only** report title that is compelling and relevant.
            * All section and subsection **titles and guidance** must be written in **formal Korean business language**.
            * Each section/subsection must include a **brief description in Korean** explaining the content and purpose.
            * Ensure the tone is suitable for a **C-level financial audience**—clear, concise, and strategic.
            * Maintain cultural and linguistic appropriateness for a banking/finance readership.

            Do not make hypothesis or assumptions on what should be included in the report.
            **IMPORTANT:** Use the **Google Search tool** to gather the most recent and relevant information to ensure the TOC supports accurate and updated content generation.
      """)     
    contents.append(Content(
          role="user",
          parts=[user_prompt]
    ))
    response = client.models.generate_content(
          model=model_id,
          contents=contents,
          config=GenerateContentConfig(
                temperature = 0.7,
                max_output_tokens = 65535,
                tools=[google_search_tool],
                response_modalities=["TEXT"],
                system_instruction=[Part.from_text(text=system_prompt)]
          )
    )
    text = response.text
    contents.append(Content(
          role="model",
          parts=[Part.from_text(text=text)]
    ))
    logger.info("✅ Table of Contents generated successfully")
    return user_prompt, text 

@retry_with_backoff(max_retries=3)
def extract_table_of_contents(context_user_prompt, context_text):
    logger.info("📋 Extracting main sections from Table of Contents...")
    user_prompt = Part.from_text(text="""From the detailed Table of Contents in Korean above, can you help me extract:
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
          model=model_id,
          contents=[
                Content(
                      role="user",
                      parts=[context_user_prompt]
                ),
                Content(
                      role="model",
                      parts=[Part.from_text(text=context_text)]
                ),
                Content(
                      role="user",
                      parts=[user_prompt]
                )
          ],
          config=GenerateContentConfig(
                temperature = 0,
                top_p = 0.95,
                seed = 0,
                max_output_tokens = 65535,
                safety_settings = [SafetySetting(
                      category="HARM_CATEGORY_HATE_SPEECH",
                      threshold="OFF"
                ),SafetySetting(
                      category="HARM_CATEGORY_DANGEROUS_CONTENT",
                      threshold="OFF"
                ),SafetySetting(
                      category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                      threshold="OFF"
                ),SafetySetting(
                      category="HARM_CATEGORY_HARASSMENT",
                      threshold="OFF"
                )],
                response_modalities=["TEXT"],
                system_instruction=[Part.from_text(text=system_prompt)]
          )
    )
    text = response.text
    logger.info("✅ Sections extracted successfully")
    return user_prompt, text 


def parse_table_of_contents(extracted_toc_text):
      """
      Parse the extracted table of contents text to get the report title and list of sections.
      
      Args:
            extracted_toc_text (str): The extracted table of contents text
            
      Returns:
            tuple: (report_title, sections_list)
                  - report_title (str): The title of the report
                  - sections_list (list): List of section titles
      """
    # Split the text into lines
      
      # Extract title
      title = None
      sections = []
      
      parts = extracted_toc_text.split('SECTIONS:')
      if len(parts) != 2:
            raise ValueError("Invalid response format")
            
            # Extract title
      title_line = parts[0].strip()
      if title_line.startswith('TITLE:'):
            title = title_line[6:].strip()
      else:
            title = "Premium Credit Card Market Analysis Report"  # Default title
            
            # Extract sections
      sections = [line.strip() for line in parts[1].split('\n') if line.strip()]
    
      return title, sections

@retry_with_backoff(max_retries=3)
def generate_section_content(section_title, section_number):
    logger.info(f"📝 Generating content for section {section_number}: {section_title}")
    user_prompt = Part.from_text(text=f"""
            Based on the guidance in the table of contents section, connect with the previous section, write a comprehensive and professionally worded section of our strategic report on the section {section_title}. 
            The content should be tailored for Kookmin Bank's Korean-speaking executive audience, including the CFO and other C-level stakeholders.
            Even though the guidance is a very useful information to write the section, please do not include the guidance in the top of the section and sub-sections.

            CRITICAL LANGUAGE REQUIREMENTS:
            - Entire content must be in formal Korean with proper business terms
            - No English allowed
            - Use Korean format for numbers, dates, currency, and percentages

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
            - Tailor content for a Korean-speaking audience, ensuring cultural and linguistic relevance


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
    contents.append(Content(
            role="user",
            parts=[user_prompt]
    ))
    response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=GenerateContentConfig(
                  tools=[google_search_tool],
                  temperature = 0,
                  max_output_tokens = 65535,
                  response_modalities=["TEXT"],
                  system_instruction=[Part.from_text(text=system_prompt)]
            )
    )

    text = response.text
    contents.append(Content(
            role="model",
            parts=[Part.from_text(text=text)]
    ))

    ## Work on the grounding search for the enrich content clarity.
    grounding_metadata = response.candidates[0].grounding_metadata
    grounding_chunks = None if grounding_metadata is None else grounding_metadata.grounding_chunks
    grounding_supports = None if grounding_metadata is None else grounding_metadata.grounding_supports
    if grounding_supports is not None and len(grounding_supports) > 0 and grounding_chunks is not None and len(grounding_chunks) > 0:
            logger.info(f"📚 Found {len(grounding_chunks)} grounding citations")
            # Sort by segment length to avoid nested replacement issues
            sorted_supports = sorted(grounding_supports, key=lambda s: len(s.segment.text), reverse=True)
            # Inline replacement with superscript links
            for support in sorted_supports:
                  segment_text = support.segment.text.strip()
                  indices = support.grounding_chunk_indices or []
                  if not indices:
                        continue

                  # Build superscript links from grounding_chunks
                  superscript_links = []
                  for i in indices:
                        try:
                              uri = grounding_chunks[i].web.uri if grounding_chunks[i].web else ""
                              # Add id to reference and link to it
                              ref_id = f"ref-{section_number}-{i+1}"
                              superscript_links.append(f'<sup><a href="#ref-section-{section_number}-{i+1}">[{section_number}.{i+1}]</a></sup>')
                        except (IndexError, AttributeError):
                              continue

                  if not superscript_links:
                        continue

                        # Join all superscript links after the matched text
                  superscript = "".join(superscript_links)
                  replacement = f"{segment_text}{superscript}"
                  pattern = re.escape(segment_text)
                  text = re.sub(pattern, replacement, text, count=1)

            # Print enriched text with sources
            section_references = "\n\n---\n" + f"#### {section_title} \n\n"
            section_references += '<div class="references-grid">\n'
            
            for idx, chunk in enumerate(grounding_chunks):
                web = chunk.web
                if web:
                    # Add id to reference entry
                    section_references = section_references + f'<div class="reference-item" id="ref-section-{section_number}-{idx+1}">{idx+1}. <a href="{web.uri}">{web.domain}</a></div>' + "\n"
                else:
                    section_references = section_references + f'<div class="reference-item" id="ref-section-{section_number}-{idx+1}">{idx+1}. No web metadata available.</div>' + "\n"
            
            section_references += '</div>\n'
            section_references = section_references + "\n---\n\n"
            report_references.append(section_references)
    else:
            logger.warning("⚠️ No grounding supports found for this section")
    logger.info(f"✅ Content generated for section {section_number}")
    return text;

@retry_with_backoff(max_retries=3)
def polish_content(content):
    logger.info("✨ Polishing content for better flow and readability...")
    user_prompt = Part.from_text(text=f"""
      You are a professional Korean editor with strong business writing experience. Improve the content’s narrative flow and transitions while preserving its language, tone, and cultural context. Return only the revised text—no introductions or explanations.

      Requirements:
      - Improve sentence flow, paragraph transitions, and overall readability
      - Maintain a professional tone for banking and financial analysis
      - Preserve all key content, analysis, terms, data, and cultural context
      - Do not alter layout (indentation, line breaks, bulleting, paragraphing)
      - Do not add introductions or explanations, just return the content
      - Keep superscript references and all HTML tags intact
      - Ensure suitability for a Korean-speaking audience
      - Maintain the original language and cultural context of the content
      - Ensure the content remains appropriate for Korean-speaking audience
      - Keep all HTML tags intact, especially those related to references

    CRITICAL: Preserve ALL superscript references (e.g., <sup><a href="#ref-section-1-1">[1.1]</a></sup>) exactly as they appear, including their HTML tags and exact placement in the text

    Content to improve:
    {content}
    """)
    
    response = client.models.generate_content(
        model=model_id,
        contents=[
            Content(
                role="user",
                parts=[user_prompt]
            )
        ],
        config=GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=65535,
            response_modalities=["TEXT"],
            safety_settings = [
                  SafetySetting(
                      category="HARM_CATEGORY_HATE_SPEECH",
                      threshold="OFF"),
                  SafetySetting(
                      category="HARM_CATEGORY_DANGEROUS_CONTENT",
                      threshold="OFF"),
                  SafetySetting(
                      category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                      threshold="OFF"),
                  SafetySetting(
                      category="HARM_CATEGORY_HARASSMENT",
                      threshold="OFF")],
            system_instruction=[Part.from_text(text=system_prompt)]
        )
    )
    
    logger.info("✅ Content polished successfully")
    return response.text

# Main execution
logger.info("🚀 Starting report generation process...")

toc_prompt, toc_text = table_of_contents_prompt()
extracted_toc_prompt, extracted_toc_text = extract_table_of_contents(toc_prompt, toc_text)
title, sections = parse_table_of_contents(extracted_toc_text)
logger.info(f"📑 Report Title: {title}")
logger.info(f"📚 Found {len(sections)} sections to process")

# Generate content for all sections except the last one
section_content = f"# {title}\n\n[TOC]\n\n"
for i, section in enumerate(sections, 1):
    content = generate_section_content(section, i)
    polished_content = polish_content(content)
    section_content += polished_content + "\n\n"
    logger.info(f"✅ Section {i}/{len(sections)} completed: {section}")

report_references = "\n\n---\n" + f"## References" + "\n\n".join(report_references)
section_content = section_content + report_references

# Save section content to markdown file
logger.info("💾 Saving content to markdown file...")
with open('section_content.md', 'w', encoding='utf-8') as f:
    f.write(section_content)
logger.info("✅ Markdown file saved successfully")

# Convert markdown to HTML
logger.info("🔄 Converting markdown to HTML...")
html_content = markdown.markdown(section_content, extensions=[
    'tables', 
    'fenced_code',
    'md_in_html',
    TocExtension(
        marker='[TOC]',
        title='Table of Contents',
        anchorlink=False,
        baselevel=1,
        toc_depth=3
    )
])

# Read and process template
logger.info("📄 Processing HTML template...")
with open('templates/report_template.html', 'r', encoding='utf-8') as f:
    template = f.read()

template = template.replace('{', '{{').replace('}', '}}')
template = template.replace('{{content}}', '{content}')
html_doc = template.format(content=html_content)

# Save HTML file
logger.info("💾 Saving HTML file...")
with open('section_content.html', 'w', encoding='utf-8') as f:
    f.write(html_doc)
logger.info("✅ HTML file saved successfully")

# Generate PDF
logger.info("🔄 Generating PDF...")
pdf_options = {
    'page-size': 'A4',
    'orientation': 'Landscape',
    'margin-top': '25mm',
    'margin-right': '25mm',
    'margin-bottom': '25mm',
    'margin-left': '25mm',
    'encoding': 'UTF-8',
    'no-outline': None
}

try:
    pdfkit.from_string(html_doc, 'section_content.pdf', options=pdf_options)
    logger.info("✅ PDF generated successfully")
except Exception as e:
    logger.error(f"❌ Error generating PDF: {str(e)}")

logger.info("🎉 Report generation process completed!")



