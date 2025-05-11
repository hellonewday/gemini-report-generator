from google import genai
import markdown
import pdfkit
import re
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Part, Content, SafetySetting
from markdown.extensions.toc import TocExtension
import logging
import csv
import os
from datetime import datetime
from google.cloud import storage

from config import REPORT_CONFIG
from utils import retry_with_backoff, initialize_request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Global variables
token_metrics = []
contents=[]
report_references = []

current_request_id = None
LOGGING_CSV = "logging.csv"


def log_token_metrics(response, section_name=""):
    """Log token usage metrics in a beautiful format"""
    if not current_request_id:
        initialize_request()
        
    input_tokens = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count
    model_name = response.model_version
    total_tokens = input_tokens + output_tokens
    
    # Set cost per 1M tokens based on model version
    if "flash" in model_name.lower():
        cost_per_1m_input = 0.15  # $0.15 per 1M tokens for input
        cost_per_1m_output = 3.5  # $3.50 per 1M tokens for output
    else:  # pro model
        cost_per_1m_input = 1.25  # $1.25 per 1M tokens for input
        cost_per_1m_output = 10.0  # $10.00 per 1M tokens for output
    
    # Calculate costs
    input_cost = round(input_tokens * cost_per_1m_input / 1000000, 6)
    output_cost = round(output_tokens * cost_per_1m_output / 1000000, 6)
    total_cost = round(input_cost + output_cost, 6)
    
    # Store metrics for final summary
    metric = {
        "request_id": current_request_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "section": section_name,
        "model_version": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_per_1m_input": cost_per_1m_input,
        "cost_per_1m_output": cost_per_1m_output,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost
    }
    token_metrics.append(metric)
    
    # Append to CSV file
    append_metric_to_csv(metric)
    
    logger.info(f"📊 Token Usage Metrics for {section_name} ({model_name}):")
    logger.info(f"   ├─ Input Tokens:  {input_tokens:,}")
    logger.info(f"   ├─ Output Tokens: {output_tokens:,}")
    logger.info(f"   └─ Total Tokens:  {total_tokens:,}")
    logger.info(f"   ├─ Input Cost:    ${input_cost:.6f}")
    logger.info(f"   └─ Output Cost:   ${output_cost:.6f}")

def append_metric_to_csv(metric):
    """Append a single metric to the logging CSV file"""
    file_exists = os.path.isfile(LOGGING_CSV)
    
    # Define CSV headers
    headers = [
        "Request ID",
        "Timestamp",
        "Section",
        "Model Version",
        "Input Tokens",
        "Output Tokens",
        "Total Tokens",
        "Cost per 1M Input ($)",
        "Cost per 1M Output ($)",
        "Input Cost ($)",
        "Output Cost ($)",
        "Total Cost ($)"
    ]
    
    try:
        with open(LOGGING_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            
            # Write header if file is new
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                "Request ID": metric["request_id"],
                "Timestamp": metric["timestamp"],
                "Section": metric["section"],
                "Model Version": metric["model_version"],
                "Input Tokens": metric["input_tokens"],
                "Output Tokens": metric["output_tokens"],
                "Total Tokens": metric["total_tokens"],
                "Cost per 1M Input ($)": metric["cost_per_1m_input"],
                "Cost per 1M Output ($)": metric["cost_per_1m_output"],
                "Input Cost ($)": metric["input_cost"],
                "Output Cost ($)": metric["output_cost"],
                "Total Cost ($)": metric["total_cost"]
            })
    except Exception as e:
        logger.error(f"❌ Error appending to logging CSV: {str(e)}")

def log_final_metrics():
    """Log a summary of all token metrics at the end of report generation"""
    if not token_metrics:
        return
        
    # Group metrics by model version
    model_metrics = {}
    for metric in token_metrics:
        model = metric["model_version"]
        if model not in model_metrics:
            model_metrics[model] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "sections": []
            }
        model_metrics[model]["input_tokens"] += metric["input_tokens"]
        model_metrics[model]["output_tokens"] += metric["output_tokens"]
        model_metrics[model]["total_tokens"] += metric["total_tokens"]
        model_metrics[model]["sections"].append(metric)
    
    # Calculate overall totals
    total_input = sum(m["input_tokens"] for m in token_metrics)
    total_output = sum(m["output_tokens"] for m in token_metrics)
    total_all = sum(m["total_tokens"] for m in token_metrics)
    total_cost = sum(m["total_cost"] for m in token_metrics)
    
    # Log overall totals
    logger.info("=" * 70)
    logger.info("📊 Overall Total Usage:")
    logger.info(f"   ├─ Total Input Tokens:  {total_input:,}")
    logger.info(f"   ├─ Total Output Tokens: {total_output:,}")
    logger.info(f"   └─ Total All Tokens:   {total_all:,}")
    logger.info(f"   └─ Total Cost:         ${total_cost:.6f}")
    logger.info("=" * 70)


client = genai.Client(
            vertexai=True,
            project="nth-droplet-458903-p4",
            location="us-central1",
        )
model_id = "gemini-2.5-pro-preview-05-06"
flash_model_id = "gemini-2.5-flash-preview-04-17"

google_search_tool = Tool(
      google_search = GoogleSearch()
)

system_prompt = f"""
    You are a senior {REPORT_CONFIG['language']} financial analyst specializing in credit card products with 20 years of experience at {REPORT_CONFIG['primary_bank']}. Your expertise spans credit card market analysis, product comparison, and competitive intelligence.

    **PRIMARY OBJECTIVE:**
    Create a comprehensive comparison of premium credit card products between {REPORT_CONFIG['primary_bank']} and its key competitors ({', '.join(REPORT_CONFIG['comparison_banks'])}), focusing on concrete product features, pricing, and benefits that drive customer decisions.

    **CRITICAL REQUIREMENTS:**

    1. LANGUAGE AND LOCALIZATION:
    - ALL content MUST be in {REPORT_CONFIG['language']} with no explanation in other languages
    - Use formal {REPORT_CONFIG['language']} business language
    - Format numbers, dates, currency, and percentages in {REPORT_CONFIG['language']}
    - Focus EXCLUSIVELY on the local market context and data
    - Do not mix data or information from different regions
    - Ensure all market data, statistics, and examples are from the local market only
    - Verify that all sources and references are from the local market

    2. CREDIT CARD COMPARISON FOCUS:
    - Detailed analysis of specific credit card products and their features
    - Direct comparison of:
        * Annual fees and charges
        * Interest rates and APR
        * Rewards programs and points structure
        * Cashback rates and categories
        * Travel benefits and insurance coverage
        * Welcome bonuses and sign-up offers
        * Foreign transaction fees
        * Credit limits and eligibility criteria
    - Clear presentation of pricing models and fee structures
    - Concrete benefits and value propositions
    - Digital features and mobile app capabilities
    - Customer service and support options

    3. RESEARCH:
    - MUST use Google Search for EVERY section
    - Verify all information with multiple sources
    - Focus on official bank websites and product pages
    - Ensure data is current and accurate
    - Prioritize local market sources and data
    - Cross-reference information with local regulatory bodies and financial institutions
    - Exclude any data or information from other regions

    4. ANALYSIS FOCUS:
    The analysis must cover these key areas:
    - Product feature comparison
    - Pricing and fee analysis
    - Benefits and rewards comparison
    - Digital capabilities
    - Customer service offerings
    - Market positioning based on concrete features
    - All analysis must be grounded in local market context

    5. KEY PERFORMANCE METRICS:
    Track and analyze these specific metrics:
    - Card issuance volume
    - Transaction volume
    - Revenue per card
    - Customer retention rate
    - Digital adoption rate
    - Market share by segment
    - All metrics must be from local market sources

    6. TARGET MARKET SEGMENTS:
    Focus analysis on these key segments:
    {', '.join(REPORT_CONFIG['market_segments'])}
    - Primary: {REPORT_CONFIG['primary_bank']} Executive Team
    - Focus on concrete product comparisons
    - Emphasis on pricing and features
    - Clear value propositions
    - Direct competitive advantages
    - All segment analysis must be based on local market data

    7. COMPETITIVE ANALYSIS:
    - Comparison banks: {', '.join(REPORT_CONFIG['comparison_banks'])}
    - Direct product feature comparison
    - Pricing strategy analysis
    - Benefits and rewards comparison
    - Digital capabilities
    - Customer experience
    - All competitive analysis must be within the local market context

    8. REPORT STRUCTURE:
    {"Follow this exact section structure:" if REPORT_CONFIG['strict_structure'] else "Following this report structure as a suggestion for the report, but you can change the structure if needed to provide strong and clear analysis."}
    {', '.join(REPORT_CONFIG['report_sections'])}

    9. WRITING STYLE:
    - Tone: {REPORT_CONFIG['writing_style']['tone']}
    - Formality: {REPORT_CONFIG['writing_style']['formality_level']}
    - Emphasis: {', '.join(REPORT_CONFIG['writing_style']['emphasis'])}
    - Clear executive summary
    - Actionable insights
    - Data visualization

    **FINAL REMINDER:**
    You MUST use Google Search for EVERY main section and ensure ALL content is in {REPORT_CONFIG['language']}. Focus on providing detailed credit card product comparisons with concrete features, pricing, and benefits that would be valuable for {REPORT_CONFIG['language']}-speaking banking executives. Avoid abstract strategic analysis and focus on actionable, concrete product comparisons. Most importantly, ensure ALL data, examples, and market information are from the local market only - do not mix data from different regions.
"""


@retry_with_backoff(max_retries=3)
def table_of_contents_prompt():
    logger.info("🔄 Generating Table of Contents...")
    user_prompt = Part.from_text(text=f"""
            Create a professional **Table of Contents** in **{REPORT_CONFIG['language']}** for an **executive-level strategic report** comparing **credit card products** from **KB Kookmin Bank**, **Hana SEB Bank**, and **Woori Bank**. This TOC will serve as a **planner for a language model** to generate the full report, so clarity, logical flow, and completeness are essential.
            The report is for the **Executives of KB Kookmin Bank** and should follow a smooth, narrative-driven structure.

            **Instructions:**

            * Write a **{REPORT_CONFIG['language']}-only** report title that is condense, aspiring, compelling and relevant
            * All main sections marked with Roman numerals (e.g., I., II., III.)
            * All section and subsection **titles and guidance** must be written in **formal {REPORT_CONFIG['language']} business language**.
            * Each section/subsection must include a **brief description in {REPORT_CONFIG['language']}** explaining the content and purpose.
            * Ensure the tone is suitable for a **C-level financial audience**—clear, concise, and strategic.
            * Maintain cultural and linguistic appropriateness for a banking/finance readership.
            * Do not include References and Appendices section in this Table of Contents.
            * **IMPORTANT:** Do not use parentheses () in section titles. Instead, use colons : or dashes - to separate additional information.

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
                temperature = 0.4,
                max_output_tokens = 65535,
                tools=[google_search_tool],
                response_modalities=["TEXT"],
                system_instruction=[Part.from_text(text=system_prompt)]
          )
    )
    text = response.text
    log_token_metrics(response, "Table of Contents Generation")
    contents.append(Content(
          role="model",
          parts=[Part.from_text(text=text)]
    ))
    logger.info("✅ Table of Contents generated successfully")
    return user_prompt, text 

@retry_with_backoff(max_retries=3)
def extract_table_of_contents(context_user_prompt, context_text):
    logger.info("📋 Extracting main sections from Table of Contents...")
    user_prompt = Part.from_text(text=f"""From the detailed Table of Contents in {REPORT_CONFIG['language']} above, can you help me extract:
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
    log_token_metrics(response, "Table of Contents Extraction")
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
    log_token_metrics(response, f"Section {section_number}: {section_title}")
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
            section_references = "\n\n" + f"#### {section_title} \n\n"
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
            logger.warning("⚠️ Agent decides not to use Google Search to this section")
    logger.info(f"✅ Content generated for section {section_number}")
    return text;

@retry_with_backoff(max_retries=3)
def polish_content(content):
    logger.info("✨ Polishing content for better flow and readability...")
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
        contents=[
            Content(
                role="user",
                parts=[user_prompt]
            )
        ],
        config=GenerateContentConfig(
            temperature=0.7,
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
    
    text = response.text
    log_token_metrics(response, "Content Polishing")
    logger.info("✅ Content polished successfully")
    return text

# Main execution
logger.info("🚀 Starting report generation process...")
initialize_request()

toc_prompt, toc_text = table_of_contents_prompt()
extracted_toc_prompt, extracted_toc_text = extract_table_of_contents(toc_prompt, toc_text)
title, sections = parse_table_of_contents(extracted_toc_text)
logger.info(f"📑 Report Title: {title}")
logger.info(f" Found {len(sections)} sections to process")

section_content = f"# {title}\n\n[TOC]\n\n"
# Generate content for first section for demo
# content = generate_section_content(sections[1], 1)
# polished_content = polish_content(content)
# section_content += polished_content + "\n\n"
# logger.info(f"✅ Demo completed: {sections[1]}")

# Generate content for all sections
for section_number, section_title in enumerate(sections, 1):
    content = generate_section_content(section_title, section_number)
    polished_content = polish_content(content)
    section_content += polished_content + "\n\n"
    logger.info(f"✅ Section {section_number} completed: {section_title}")

report_references = "\n\n---\n" + f"## References" + "\n\n".join(report_references)
section_content = section_content + report_references

# Create reports directory if it doesn't exist
reports_dir = 'reports'
os.makedirs(reports_dir, exist_ok=True)

# Generate unique filename using timestamp, request ID, and language
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
base_filename = f"{timestamp}_{current_request_id}_{REPORT_CONFIG['language'].lower()}"
md_file = os.path.join(reports_dir, f"{base_filename}.md")
html_file = os.path.join(reports_dir, f"{base_filename}.html")
pdf_file = os.path.join(reports_dir, f"{base_filename}.pdf")

# Save section content to markdown file
logger.info("💾 Saving content to markdown file...")
with open(md_file, 'w', encoding='utf-8') as f:
    f.write(section_content)
logger.info(f"✅ Markdown file saved successfully: {md_file}")

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

# Add section breaks before each h2
html_content = re.sub(r'<h2', '<div class="section-break"></div><h2', html_content)

# Get orientation from config with validation
orientation = REPORT_CONFIG.get('orientation', 'landscape').lower()
if orientation not in ['landscape', 'portrait']:
    logger.warning(f"⚠️ Invalid orientation: {orientation}. Defaulting to landscape.")
    orientation = 'landscape'

# Select template based on orientation
template_file = f"report_template{'_portrait' if orientation == 'portrait' else ''}.html"
template_path = f'templates/{template_file}'

# Read and process template
logger.info(f"📄 Processing HTML template for {orientation} orientation: {template_path}")
try:
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
except FileNotFoundError:
    logger.error(f"❌ Template file '{template_path}' not found. Falling back to default template.")
    template_path = 'templates/report_template.html'
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

template = template.replace('{', '{{').replace('}', '}}')
template = template.replace('{{content}}', '{content}')
html_doc = template.format(content=html_content)

# Save HTML file
logger.info("💾 Saving HTML file...")
with open(html_file, 'w', encoding='utf-8') as f:
    f.write(html_doc)
logger.info(f"✅ HTML file saved successfully: {html_file}")

# Generate PDF
logger.info("🔄 Generating PDF...")
pdf_options = {
    'page-size': 'A4',
    'orientation': orientation.capitalize(),
    'margin-top': '25mm',
    'margin-right': '25mm',
    'margin-bottom': '25mm',
    'margin-left': '25mm',
    'encoding': 'UTF-8',
    'no-outline': None
}

try:

    pdfkit.from_string(html_doc, pdf_file, options=pdf_options)
    logger.info(f"✅ PDF generated successfully: {pdf_file}")
    
    # Upload to Google Cloud Storage
    logger.info("📤 Uploading PDF to Google Cloud Storage...")
    from google.cloud import storage
    
    # Initialize the client
    storage_client = storage.Client(project="nth-droplet-458903-p4")
    bucket = storage_client.bucket('credit-card-reports')
    
    # Upload PDF file to language-specific folder
    language_folder = REPORT_CONFIG['language'].lower()
    blob_name = f"{language_folder}/{os.path.basename(pdf_file)}"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(pdf_file, content_type='application/pdf')
    blob.make_public()
    
    # Get the public URL
    public_url = blob.public_url
    logger.info(f"✅ PDF uploaded successfully to {language_folder} folder: {blob_name}")
    logger.info(f"🔗 Public URL: {public_url}")
    
except Exception as e:
    logger.error(f"❌ Error in PDF generation or upload: {str(e)}")

# Log final metrics summary
log_final_metrics()
logger.info("🎉 Report generation process completed!")



