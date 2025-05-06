"""
Report Generator Application

This module provides functionality to generate professional reports using the Gemini API.
It handles report generation, formatting, and PDF conversion with proper styling.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, NamedTuple

import pdfkit
from google import genai
from google.genai import types
from markdown import markdown
from markdown.extensions.toc import TocExtension

# Constants
DEFAULT_MARKERS = {
    'primary': ("\n\n***\n\n", "\n\n***\n\n"),
    'secondary': ("\n\n---\n\n", "\n\n---\n\n")
}

SKIP_PARAPHRASING_SECTIONS = ['appendix', 'appendices', 'references']

class ReportSection(NamedTuple):
    """Represents a section in the report."""
    title: str
    content: str

class ReportGenerator:
    """Main class for generating professional reports using Gemini API."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the ReportGenerator with configuration."""
        self.client = genai.Client(
            vertexai=True,
            project="nth-droplet-458903-p4",
            location="global",
        )
        self.model = "gemini-2.5-pro-preview-03-25"
        self.system_instruction = self._get_system_instruction()
        self.config = self._get_default_config()
        if config:
            self.config.update(config)
        
        self.conversation_history: List[types.Content] = []
        self.current_report_id: Optional[str] = None
        
        self.setup_logging()
        self.create_directories()

    def _get_system_instruction(self) -> str:
        """Get the system instruction for the Gemini model."""
        return """You are a senior financial research analyst and business writer in the executive strategy office of Kookmin Bank (KB) in Korea. Your task is to produce highly professional, CFO-ready reports that offer deep comparative analysis of premium credit card products between Kookmin Bank and its major competitors.

        Your audience includes the CFO and C-level executives of Kookmin Bank. All reports must meet the highest standards of strategic clarity, analytical depth, and visual presentation. The writing must adopt an executive tone — formal, insight-driven, and fluent — while also maintaining a smooth narrative flow with well-connected paragraphs and transitions.

        Key aspects to focus on:
        - Strategic insights and actionable recommendations
        - Clear comparative analysis with competitors
        - Data-driven decision support
        - Professional and engaging presentation
        - Logical flow and narrative coherence"""

    def _get_default_config(self) -> Dict[str, Any]:
        """Get the default configuration for the report generator."""
        return {
            'max_retries': 3,
            'retry_delay': 5,
            'temperature': 0.3,
            'top_p': 0.95,
            'max_output_tokens': 65535,
            'save_history': True,
            'history_dir': 'history',
            'reports_dir': 'reports',
            'log_level': logging.INFO,
        }

    def extract_content_between_markers(
        self,
        text: str,
        start_marker: Optional[str] = None,
        end_marker: Optional[str] = None
    ) -> str:
        """Extract content between specified markers."""
        try:
            if start_marker is None or end_marker is None:
                start_marker, end_marker = DEFAULT_MARKERS['primary']
                start_idx = text.find(start_marker)
                if start_idx == -1:
                    start_marker, end_marker = DEFAULT_MARKERS['secondary']
                    start_idx = text.find(start_marker)
            
            if start_idx == -1:
                return text
            
            start_idx += len(start_marker)
            end_idx = text.find(end_marker, start_idx)
            return text[start_idx:end_idx].strip() if end_idx != -1 else text[start_idx:].strip()
        except Exception as e:
            self.logger.error(f"Error extracting content between markers: {e}")
            return text

    def setup_logging(self) -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=self.config['log_level'],
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('report_generator.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        for directory in [self.config['history_dir'], self.config['reports_dir']]:
            Path(directory).mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created directory: {directory}")

    def add_to_history(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.conversation_history.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=content)]
            )
        )
        self.logger.debug(f"Added {role} message to history")

    def save_conversation_history(self) -> None:
        """Save the current conversation history to a file."""
        if not self.config['save_history'] or not self.current_report_id:
            return
            
        history_file = Path(self.config['history_dir']) / f'conversation_{self.current_report_id}.json'
        serializable_history = [
            {'role': content.role, 'parts': [part.text for part in content.parts]}
            for content in self.conversation_history
        ]
        
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_history, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved conversation history to {history_file}")
        except Exception as e:
            self.logger.error(f"Error saving conversation history: {e}")

    def _get_generate_content_config(self, system_instruction: Optional[str] = None) -> types.GenerateContentConfig:
        """Get the configuration for content generation."""
        return types.GenerateContentConfig(
            temperature=self.config['temperature'],
            top_p=self.config['top_p'],
            seed=0,
            max_output_tokens=self.config['max_output_tokens'],
            response_modalities=["TEXT"],
            safety_settings=[
                types.SafetySetting(category=category, threshold="OFF")
                for category in [
                    "HARM_CATEGORY_HATE_SPEECH",
                    "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "HARM_CATEGORY_HARASSMENT"
                ]
            ],
            tools=[types.Tool(google_search=types.GoogleSearch())],
            system_instruction=[types.Part.from_text(text=system_instruction or self.system_instruction)],
        )

    def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None
    ) -> str:
        """Generate content using the Gemini model with retry logic."""
        self.add_to_history("user", prompt)
        
        for attempt in range(self.config['max_retries']):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=self.conversation_history,
                    config=self._get_generate_content_config(system_instruction),
                )
                
                if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
                    raise Exception("Empty response from model")
                
                response_text = response.candidates[0].content.parts[0].text
                self.add_to_history("model", response_text)
                
                if self.config['save_history']:
                    self.save_conversation_history()
                
                return response_text
                
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.config['max_retries'] - 1:
                    delay = self.config['retry_delay'] * (1 + random.random())
                    self.logger.info(f"Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
                else:
                    self.logger.error("All retry attempts failed")
                    raise

    def _get_html_template(self, content: str) -> str:
        """Get the HTML template with embedded CSS."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: landscape;
                    margin: 2.5cm;
                }}
                
                body {{
                    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                    font-size: 16px;
                    line-height: 1.7;
                    color: #2c3e50;
                    margin: 0;
                    padding: 0;
                }}

                /* Container for content */
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 0 2rem;
                }}

                /* Titles */
                h1 {{
                    color: #154360;
                    font-size: 2.5em;
                    text-align: center;
                    margin-bottom: 1.2em;
                    border-bottom: 4px solid #154360;
                    padding-bottom: 0.5em;
                    letter-spacing: 0.5px;
                    page-break-after: always;
                }}
                
                h2 {{
                    color: #1f618d;
                    font-size: 1.8em;
                    margin-top: 2em;
                    margin-bottom: 0.8em;
                    padding-left: 0.5em;
                    border-left: 5px solid #1f618d;
                    padding: 0.3em 0.6em;
                    page-break-before: always;
                }}
                
                h3 {{
                    color: #2980b9;
                    font-size: 1.4em;
                    margin-top: 1.5em;
                    margin-bottom: 0.6em;
                }}
                
                /* Paragraphs */
                p {{
                    text-align: justify;
                    margin-bottom: 1.2em;
                }}
                
                /* Tables */
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 2em 0;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
                    border-radius: 6px;
                    overflow: hidden;
                    page-break-inside: avoid;
                }}
                
                th {{
                    background-color: #154360;
                    color: white;
                    padding: 14px;
                    text-align: left;
                    font-weight: bold;
                }}
                
                td {{
                    padding: 12px;
                    border-bottom: 1px solid #ddd;
                }}
                
                tr:nth-child(even) {{
                    background-color: #f4f6f7;
                }}
                
                tr:hover {{
                    background-color: #e5e8e8;
                }}
                
                /* TOC */
                .toc {{
                    padding: 1.5em;
                    margin: 2em 0;
                    border-left: 4px solid #154360;
                    border-radius: 4px;
                    page-break-after: always;
                }}
                
                .toc h2 {{
                    margin-top: 0;
                    color: #154360;
                }}
                
                .toc ul {{
                    list-style-type: none;
                    padding-left: 1em;
                }}
                
                .toc li {{
                    margin: 0.5em 0;
                }}
                
                /* Links */
                a {{
                    color: #1f618d;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                
                /* Blockquote */
                blockquote {{
                    background-color: #f0f3f4;
                    border-left: 5px solid #2980b9;
                    padding: 1em 1.5em;
                    font-style: italic;
                    margin: 1.5em 0;
                }}
                
                /* Code */
                code {{
                    background-color: #f0f0f0;
                    padding: 0.2em 0.4em;
                    font-family: 'Courier New', monospace;
                    border-radius: 4px;
                }}
                
                pre {{
                    background-color: #f0f0f0;
                    padding: 1em;
                    border-radius: 4px;
                    overflow-x: auto;
                }}
                
                /* Images */
                img {{
                    max-width: 100%;
                    height: auto;
                    display: block;
                    margin: 2em auto;
                    page-break-inside: avoid;
                }}

                /* Lists */
                ul, ol {{
                    margin: 1em 0 1em 2em;
                }}

                li {{
                    margin: 0.5em 0;
                }}

                /* Footnotes & References */
                .footnotes {{
                    margin-top: 2em;
                    padding-top: 1em;
                    border-top: 1px solid #ccc;
                    font-size: 0.9em;
                    page-break-before: always;
                }}

                .section {{
                    margin-bottom: 2em;
                }}

                sup {{
                    vertical-align: super;
                    font-size: smaller;
                }}

                /* Page break */
                .page-break {{
                    page-break-after: always;
                }}

                /* Media Queries for Responsive Design */
                @media screen and (max-width: 1200px) {{
                    .container {{
                        max-width: 100%;
                        padding: 0 1.5rem;
                    }}
                }}

                @media screen and (max-width: 768px) {{
                    .container {{
                        padding: 0 1rem;
                    }}
                    
                    h1 {{
                        font-size: 2em;
                    }}
                    
                    h2 {{
                        font-size: 1.6em;
                    }}
                    
                    h3 {{
                        font-size: 1.2em;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                {content}
            </div>
        </body>
        </html>
        """

    def _get_pdf_options(self) -> Dict[str, Any]:
        """Get PDF generation options."""
        return {
            'page-size': 'A4',
            'orientation': 'Landscape',
            'margin-top': '2.5cm',
            'margin-right': '2.5cm',
            'margin-bottom': '2.5cm',
            'margin-left': '2.5cm',
            'encoding': 'UTF-8',
            'no-outline': None,
            'enable-local-file-access': None,
        }

    def generate_table_of_contents(self) -> str:
        """Generate and format the table of contents."""
        toc_prompt = """
        Create a professional, concise Table of Contents for a strategic report titled with a creative and fitting name. The report compares premium credit card offerings from KB Kookmin Bank, Hana, Woori, and Shinhan Bank, and is intended for executive readers at KB Kookmin Bank, including the CFO. 

        The Table of Contents should follow a narrative structure, suitable for a business magazine or investor presentation, and use Roman numerals for main sections with clearly indented subsections.

        The TOC must include:
        - An introduction on market dynamics and the strategic importance of premium credit card competition.
        - A focused analysis of KB Kookmin Bank's premium card offerings, emphasizing positioning and innovation.
        - A comparative evaluation of Hana, Woori, and Shinhan's offerings, covering features, fees, rewards, digital experience, target customers, and differentiation.
        - A synthesis of strategic insights including profitability, risks, and emerging market trends.
        - Actionable recommendations for securing competitive advantage and driving growth.
        - A references section.

        Ensure the Table of Contents is logically organized, reader-friendly, and appropriate for executive-level decision-making. Do not add any introductory phrases or explanations to your response
        """
        
        toc_response = self.generate_content(toc_prompt)
        return self.extract_content_between_markers(toc_response)

    def generate_section_content(self, section_title: str, previous_sections: Optional[List[ReportSection]] = None) -> str:
        """Generate content for a specific section."""
        try:
            # Create context from previous sections
            context = ""
            if previous_sections:
                context = "\n".join([
                    f"- {section.title}: {section.content[:200]}..."  # Limit context length
                    for section in previous_sections[-3:]  # Only use last 3 sections for context
                ])
            
            # Create anchor link from section title
            anchor_text = re.sub(r'[^a-z0-9]+', '-', section_title.lower()).strip('-')
            
            section_prompt = f"""
            {context}

            Write a comprehensive and professionally worded section of our strategic report on the topic: **{section_title}**. The content should be tailored for KB Bank's executive audience, particularly the CFO and C-level executives.

            Writing Style Requirements:
            1. Use a flowing, narrative style with well-connected paragraphs
            2. Focus on creating a compelling story that builds momentum
            3. Use transition phrases to connect ideas and maintain flow
            4. Incorporate strategic insights and actionable recommendations
            5. Maintain a professional yet engaging tone
            6. Use data and analysis to support key points
            7. Include clear calls to action where appropriate

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
            
            section_response = self.generate_content(section_prompt)
            content = self.extract_content_between_markers(section_response)
            
            if not content:
                self.logger.warning(f"Empty content generated for section: {section_title}")
                return f"## {section_title}\n\n*Content generation failed. Please try again.*"
            
            # Ensure the first heading matches the section title format
            lines = content.split('\n')
            if lines and not lines[0].startswith('##'):
                lines[0] = f"## {section_title}"
            
            # Clean up any excessive blank lines and ensure proper spacing
            cleaned_lines = []
            prev_blank = False
            for line in lines:
                is_blank = not line.strip()
                if not (is_blank and prev_blank):  # Don't add consecutive blank lines
                    cleaned_lines.append(line)
                prev_blank = is_blank
            
            # Ensure proper spacing around headings
            final_lines = []
            for i, line in enumerate(cleaned_lines):
                if line.startswith('#'):
                    if i > 0 and cleaned_lines[i-1].strip():
                        final_lines.append('')
                    final_lines.append(line)
                    if i < len(cleaned_lines)-1 and cleaned_lines[i+1].strip():
                        final_lines.append('')
                else:
                    final_lines.append(line)
            
            return '\n'.join(final_lines)
            
        except Exception as e:
            self.logger.error(f"Error generating section content for {section_title}: {e}")
            return f"## {section_title}\n\n*Error generating content: {str(e)}*"

    def generate_references_section(self, report: List[ReportSection]) -> str:
        """Generate the references section based on citations found in the report."""
        citations = set()
        for section in report:
            citations.update(re.findall(r'\[(\d+)\]', section.content))
        
        if not citations:
            return "No references cited in the report."
        
        references_prompt = f"""You are a financial research analyst. Generate a comprehensive References section for the report based on the following citation numbers: {sorted(citations)}.

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

        Do not include introductory phrases, explanations, or commentary—only the numbered list of formatted references.
        Ensure consistent formatting across all references."""
                
        references_response = self.generate_content(references_prompt)
        return self.extract_content_between_markers(references_response)

    def process_report(self, resume_from: Optional[str] = None) -> Tuple[List[ReportSection], str]:
        """Process the report, with optional resume functionality."""
        start_time = time.time()
        
        if resume_from:
            if not self.load_conversation_history(resume_from):
                self.logger.error("❌ Unable to resume from the previous report. Starting fresh...")
                return [], ""
            self.current_report_id = resume_from
            self.logger.info("✅ Successfully loaded previous report state")
        else:
            self.conversation_history = []
            self.current_report_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.logger.info("📝 Starting new report generation...")
        
        self.logger.info("📋 Creating Table of Contents...")
        toc = self.generate_table_of_contents()
        self.logger.info("✅ Table of Contents created successfully")
        
        # Extract sections from TOC
        self.logger.info("🔍 Analyzing Table of Contents structure...")
        report_title, section_titles = self.extract_sections_from_toc(toc)
        self.logger.info(f"📚 Report Title: {report_title}")
        
        if not section_titles:
            self.logger.warning("⚠️ No sections found in the Table of Contents")
            return [], toc
        
        self.logger.info(f"📑 Found {len(section_titles)} sections to process")
        
        # Generate content for each section
        processed_sections = []
        total_sections = len(section_titles)
        
        for i, section_title in enumerate(section_titles, 1):
            try:
                self.logger.info(f"\n📝 Processing Section {i}/{total_sections}: {section_title}")
                
                # Calculate progress and estimated time
                elapsed_time = time.time() - start_time
                avg_time_per_section = elapsed_time / i if i > 0 else 0
                remaining_sections = total_sections - i
                estimated_remaining = avg_time_per_section * remaining_sections
                
                if estimated_remaining > 0:
                    self.logger.info(f"⏳ Estimated time remaining: {estimated_remaining/60:.1f} minutes")
                
                # Generate content for the section
                self.logger.info("📊 Generating content...")
                content = self.generate_section_content(
                    section_title,
                    processed_sections  # Pass previous sections for context
                )
                
                # Skip polishing for specific sections
                section_lower = section_title.lower()
                if any(skip_section in section_lower for skip_section in SKIP_PARAPHRASING_SECTIONS):
                    self.logger.info("⏭️ Skipping content polishing for this section")
                    processed_sections.append(ReportSection(
                        title=section_title,
                        content=content
                    ))
                else:
                    # Polish the content
                    self.logger.info("✨ Polishing content...")
                    polish_prompt = f"""You are a professional editor. Your task is to improve the following content by enhancing its narrative flow and transitions. Return ONLY the improved content without any introductory phrases or explanations.

                    Requirements:
                    - Make sentences flow more smoothly
                    - Improve transitions between paragraphs
                    - Maintain a professional tone, suitable for banking and financial analysis
                    - Preserve all key information and analysis
                    - Keep specialized terms and data unchanged
                    - Focus on grammar, vocabulary, coherence, and readability
                    - Do not make any changes to the layout such as indentations, line breaks, transform into bullet points or paragraph breaks
                    - Do not add any introductory phrases or explanations to your response

                    Content to improve:
                    {content}"""
                    
                    try:
                        polished_response = self.generate_content(polish_prompt)
                        polished_content = self.extract_content_between_markers(polished_response)
                        processed_sections.append(ReportSection(
                            title=section_title,
                            content=polished_content
                        ))
                        self.logger.info("✅ Content polished successfully")
                    except Exception as e:
                        self.logger.error(f"❌ Error polishing content: {str(e)}")
                        processed_sections.append(ReportSection(
                            title=section_title,
                            content=content
                        ))
                
                self.logger.info(f"✅ Section {i}/{total_sections} completed")
                
            except Exception as e:
                self.logger.error(f"❌ Error processing section {section_title}: {str(e)}")
                # Add error section to maintain structure
                processed_sections.append(ReportSection(
                    title=section_title,
                    content=f"## {section_title}\n\n*Error processing section: {str(e)}*"
                ))
        
        total_time = time.time() - start_time
        self.logger.info(f"\n🎉 Report generation completed in {total_time/60:.1f} minutes")
        
        return processed_sections, toc

    def extract_sections_from_toc(self, toc: str) -> Tuple[str, List[str]]:
        """Extract report title and sections from the table of contents using LLM."""
        prompt = f"""
            Given the Table of Contents below, extract:
            1. The main report title (first line)
            2. All main sections marked with Roman numerals (e.g., I., II., III.)

            Return in this format:
            TITLE: [Report Title]
            SECTIONS:
            [Section 1]
            [Section 2]
            [Section 3]

            Input:
            {toc}
        """

        try:
            response = self.generate_content(prompt, system_instruction="You are a helpful assistant that extracts titles and section names from table of contents.")
            
            # Split response into title and sections
            parts = response.split('SECTIONS:')
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
            
            self.logger.info(f"Extracted title: {title}")
            self.logger.info(f"Extracted {len(sections)} sections from TOC")
            
            return title, sections
        except Exception as e:
            self.logger.error(f"Error extracting sections from TOC: {e}")
            # Fallback to regex extraction
            sections = re.findall(r'[IVX]+\.\s+(.*?)(?=\n[IVX]+\.|\Z)', toc, re.DOTALL)
            return "Premium Credit Card Market Analysis Report", [section.strip() for section in sections]

    def save_to_markdown(
        self,
        report: List[ReportSection],
        toc: str
    ) -> Tuple[str, str, str]:
        """Save the report to markdown, HTML, and convert to PDF."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f'credit_card_analysis_{timestamp}'
        md_filename = Path(self.config['reports_dir']) / f'{base_filename}.md'
        html_filename = Path(self.config['reports_dir']) / f'{base_filename}.html'
        
        try:
            # Extract report title and sections from TOC
            report_title, _ = self.extract_sections_from_toc(toc)
            
            self.logger.info(f"\n📄 Saving report: {report_title}")
            
            # Start with main title and TOC marker
            md_content = f"# {report_title}\n\n[TOC]\n\n"
            
            # Add all sections
            for section in report:
                # Extract first line from content and use it as title
                content_lines = section.content.split('\n')
                if content_lines:
                    section_title = content_lines[0].strip()
                    # Remove the first line from content if it's a heading
                    if section_title.startswith('#'):
                        section_content = '\n'.join(content_lines[1:]).strip()
                    else:
                        section_content = section.content
                else:
                    section_title = section.title
                    section_content = section.content
                
                # Add section with proper heading
                md_content += f"{section_title}\n\n"
                md_content += section_content
                md_content += "\n\n---\n\n"
            
            # Generate and add references section
            # self.logger.info("📚 Generating References section...")
            # references_content = self.generate_references_section(report)
            # md_content += "## References\n\n"
            # md_content += references_content
            
            # Save markdown file
            with open(md_filename, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            self.logger.info(f"✅ Markdown file saved: {md_filename}")
            
            # Generate HTML
            self.logger.info("🔄 Converting to HTML...")
            html_content = markdown(md_content, extensions=['tables', 'fenced_code', 'md_in_html', TocExtension(
                marker='[TOC]',
                title='Table of Contents',
                anchorlink=False,
                baselevel=1,
                toc_depth=3
            )])
            
            # Save HTML file
            with open(html_filename, 'w', encoding='utf-8') as f:
                f.write(self._get_html_template(html_content))
            
            self.logger.info(f"✅ HTML file saved: {html_filename}")
            
            # Generate PDF
            pdf_filename = Path(self.config['reports_dir']) / f'{base_filename}.pdf'
            self.logger.info("🔄 Converting to PDF...")
            
            try:
                pdfkit.from_file(str(html_filename), pdf_filename, options=self._get_pdf_options())
                self.logger.info(f"✅ PDF generated: {pdf_filename}")
            except Exception as e:
                self.logger.error(f"❌ Error generating PDF: {str(e)}")
                raise
            
            self.logger.info("\n🎉 Report generation complete!")
            self.logger.info(f"📄 Markdown file: {md_filename}")
            self.logger.info(f"🌐 HTML file: {html_filename}")
            self.logger.info(f"📑 PDF file: {pdf_filename}")
            
            return str(md_filename), str(html_filename), str(pdf_filename)
            
        except Exception as e:
            self.logger.error(f"❌ Error saving report: {str(e)}")
            raise

    def load_conversation_history(self, report_id: str) -> bool:
        """Load conversation history from a file."""
        history_file = Path(self.config['history_dir']) / f'conversation_{report_id}.json'
        
        if not Path(history_file).exists():
            return False
            
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            self.conversation_history = [
                types.Content(
                    role=item['role'],
                    parts=[types.Part.from_text(text=part) for part in item['parts']]
                )
                for item in history_data
            ]
            
            self.current_report_id = report_id
            self.logger.info(f"Loaded conversation history from {history_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error loading conversation history: {e}")
            return False


def main() -> None:
    """Main entry point for the report generator."""
    generator = ReportGenerator()
    report, toc = generator.process_report()
    md_file, html_file, pdf_file = generator.save_to_markdown(report, toc)
    
    print(f"\nReport has been generated and saved to:")
    print(f"Markdown: {md_file}")
    print(f"HTML: {html_file}")
    print(f"PDF: {pdf_file}")


if __name__ == "__main__":
    main()