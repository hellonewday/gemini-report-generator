"""
Report Generator Application

This module provides functionality to generate professional reports using the Gemini API.
It handles report generation, formatting, and PDF conversion with proper styling.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import random
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pdfkit
from google import genai
from google.genai import types
from markdown import markdown


class ReportGenerator:
    """Main class for generating professional reports using Gemini API."""

    def __init__(self, config: Optional[Dict] = None) -> None:
        """Initialize the ReportGenerator with configuration.

        Args:
            config: Optional configuration dictionary to override defaults.
        """
        self.client = genai.Client(
            vertexai=True,
            project="nth-droplet-458903-p4",
            location="global",
        )
        self.model = "gemini-2.5-pro-preview-03-25"
        self.system_instruction = self._get_system_instruction()
        
        # Initialize configuration with defaults
        self.config = self._get_default_config()
        if config:
            self.config.update(config)
        
        # Initialize conversation history and report tracking
        self.conversation_history: List[types.Content] = []
        self.current_report_id: Optional[str] = None
        
        # Setup logging and create necessary directories
        self.setup_logging()
        self.create_directories()

    def _get_system_instruction(self) -> str:
        """Get the system instruction for the Gemini model.

        Returns:
            str: The system instruction text.
        """
        return """You are a senior financial research analyst and business writer in the executive strategy office of KB Kookmin Bank. Your task is to produce highly professional, CFO-ready reports that offer deep comparative analysis of premium credit card products between KB Kookmin Bank and its major competitors.

Your audience includes the CFO and C-level executives of the bank. All reports must meet the highest standards of strategic clarity, analytical depth, and visual presentation. The writing must adopt an executive tone — formal, insight-driven, and fluent — while also maintaining a smooth narrative flow with well-connected paragraphs and transitions.

Key aspects to focus on:
- Strategic insights and actionable recommendations
- Clear comparative analysis with competitors
- Data-driven decision support
- Professional and engaging presentation
- Logical flow and narrative coherence"""

    def _get_default_config(self) -> Dict:
        """Get the default configuration for the report generator.

        Returns:
            Dict: Default configuration dictionary.
        """
        return {
            'max_retries': 3,
            'retry_delay': 5,
            'temperature': 0.6,
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
        """Extract content between specified markers.

        Args:
            text: The text to extract content from.
            start_marker: Optional start marker. If None, tries both *** and ---.
            end_marker: Optional end marker. If None, tries both *** and ---.

        Returns:
            str: The extracted content.
        """
        try:
            if start_marker is None or end_marker is None:
                start_idx = text.find("\n\n***\n\n")
                if start_idx != -1:
                    start_marker = "\n\n***\n\n"
                    end_marker = "\n\n***\n\n"
                else:
                    start_marker = "\n\n---\n\n"
                    end_marker = "\n\n---\n\n"
                    start_idx = text.find(start_marker)
            
            if start_idx == -1:
                return text
            
            start_idx += len(start_marker)
            end_idx = text.find(end_marker, start_idx)
            
            if end_idx == -1:
                return text[start_idx:].strip()
            
            return text[start_idx:end_idx].strip()
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
        """Add a message to the conversation history.

        Args:
            role: The role of the message sender (user/model).
            content: The content of the message.
        """
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
        
        serializable_history = []
        for content in self.conversation_history:
            serializable_history.append({
                'role': content.role,
                'parts': [part.text for part in content.parts]
            })
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_history, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Saved conversation history to {history_file}")

    def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None
    ) -> str:
        """Generate content using the Gemini model with retry logic.

        Args:
            prompt: The prompt to generate content from.
            system_instruction: Optional system instruction to override default.

        Returns:
            str: The generated content.

        Raises:
            Exception: If all retry attempts fail.
        """
        self.add_to_history("user", prompt)
        
        tools = [types.Tool(google_search=types.GoogleSearch())]
        
        generate_content_config = types.GenerateContentConfig(
            temperature=self.config['temperature'],
            top_p=self.config['top_p'],
            seed=0,
            max_output_tokens=self.config['max_output_tokens'],
            response_modalities=["TEXT"],
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
            ],
            tools=tools,
            system_instruction=[types.Part.from_text(text=system_instruction or self.system_instruction)],
        )

        for attempt in range(self.config['max_retries']):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=self.conversation_history,
                    config=generate_content_config,
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
        """Get the HTML template with embedded CSS.

        Args:
            content: The content to be included in the HTML.

        Returns:
            str: The complete HTML template.
        """
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
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #fff;
                }}
                
                h1 {{
                    color: #1a5276;
                    border-bottom: 3px solid #1a5276;
                    padding-bottom: 0.5em;
                    margin-bottom: 1em;
                    font-size: 2.2em;
                    text-align: center;
                }}
                
                h2 {{
                    color: #2874a6;
                    margin-top: 1.8em;
                    margin-bottom: 0.8em;
                    font-size: 1.6em;
                    border-left: 4px solid #2874a6;
                    padding-left: 0.5em;
                }}
                
                h3 {{
                    color: #3498db;
                    margin-top: 1.5em;
                    margin-bottom: 0.6em;
                    font-size: 1.3em;
                }}
                
                p {{
                    margin-bottom: 1em;
                    text-align: justify;
                }}
                
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1.5em 0;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }}
                
                th {{
                    background-color: #1a5276;
                    color: white;
                    padding: 12px;
                    text-align: left;
                    font-weight: 600;
                }}
                
                td {{
                    padding: 10px;
                    border: 1px solid #ddd;
                }}
                
                tr:nth-child(even) {{
                    background-color: #f8f9fa;
                }}
                
                tr:hover {{
                    background-color: #f1f1f1;
                }}
                
                .toc {{
                    margin: 2em 0;
                    padding: 1em;
                    background-color: #f8f9fa;
                    border-left: 4px solid #1a5276;
                }}
                
                .toc h2 {{
                    margin-top: 0;
                    color: #1a5276;
                }}
                
                .toc ul {{
                    list-style-type: none;
                    padding-left: 1em;
                }}
                
                .toc li {{
                    margin: 0.5em 0;
                }}
                
                .toc a {{
                    color: #2874a6;
                    text-decoration: none;
                }}
                
                .toc a:hover {{
                    text-decoration: underline;
                }}
                
                blockquote {{
                    margin: 1.5em 0;
                    padding: 1em 1.5em;
                    background-color: #f8f9fa;
                    border-left: 4px solid #3498db;
                    font-style: italic;
                }}
                
                code {{
                    background-color: #f8f9fa;
                    padding: 0.2em 0.4em;
                    border-radius: 3px;
                    font-family: 'Courier New', monospace;
                }}
                
                pre {{
                    background-color: #f8f9fa;
                    padding: 1em;
                    border-radius: 4px;
                    overflow-x: auto;
                }}
                
                img {{
                    max-width: 100%;
                    height: auto;
                    display: block;
                    margin: 1.5em auto;
                }}
                
                .page-break {{
                    page-break-after: always;
                }}
            </style>
        </head>
        <body>
            {content}
        </body>
        </html>
        """

    def save_to_markdown(
        self,
        report: List[Dict],
        toc: str
    ) -> Tuple[str, str]:
        """Save the report to markdown and convert to PDF.

        Args:
            report: The report content as a list of dictionaries.
            toc: The table of contents.

        Returns:
            Tuple[str, str]: Paths to the markdown and PDF files.

        Raises:
            Exception: If there's an error saving the report.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f'credit_card_analysis_{timestamp}'
        
        # Save markdown file
        md_filename = Path(self.config['reports_dir']) / f'{base_filename}.md'
        
        try:
            # Create markdown content
            md_content = "# Premium Credit Card Market Analysis Report\n\n"
            md_content += "## Table of Contents\n\n"
            md_content += toc
            md_content += "\n\n---\n\n"
            
            for section in report:
                md_content += f"## {section['title']}\n\n"
                md_content += section['content']
                md_content += "\n\n---\n\n"
            
            # Save markdown file
            with open(md_filename, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            self.logger.info(f"Report saved to: {md_filename}")
            
            # Convert to PDF
            pdf_filename = Path(self.config['reports_dir']) / f'{base_filename}.pdf'
            
            # Create HTML content
            html_content = markdown(md_content, extensions=['tables', 'fenced_code'])
            
            # Create temporary HTML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as html_file:
                html_file.write(self._get_html_template(html_content))
                html_path = html_file.name
            
            try:
                # Configure pdfkit options
                options = {
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
                
                # Generate PDF
                pdfkit.from_file(html_path, pdf_filename, options=options)
                self.logger.info(f"PDF generated: {pdf_filename}")
            finally:
                # Clean up temporary HTML file
                os.unlink(html_path)
            
            return str(md_filename), str(pdf_filename)
            
        except Exception as e:
            self.logger.error(f"Error saving report: {e}")
            raise

    def extract_sections_from_toc(self, toc: str) -> List[str]:
        """Extract sections from the table of contents using LLM"""
        prompt = f"""Given the following table of contents, extract all main sections (marked with Roman numerals) and their full titles. Return them as a list, one per line, without any additional formatting or numbering:

{toc}

Example output format:
Section 1 Title
Section 2 Title
Section 3 Title"""
        
        try:
            response = self.generate_content(prompt, system_instruction="You are a helpful assistant that extracts section titles from table of contents.")
            sections = [line.strip() for line in response.split('\n') if line.strip()]
            self.logger.info(f"Extracted {len(sections)} sections from TOC")
            return sections
        except Exception as e:
            self.logger.error(f"Error extracting sections from TOC: {e}")
            # Fallback to regex if LLM extraction fails
            sections = re.findall(r'[IVX]+\.\s+(.*?)(?=\n[IVX]+\.|\Z)', toc, re.DOTALL)
            return [section.strip() for section in sections]

    def format_toc(self, toc: str) -> str:
        """Format the table of contents with proper spacing"""
        lines = toc.split('\n')
        formatted_lines = []
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                formatted_lines.append(line)
                continue
                
            # Check if line is a main section (Roman numeral)
            if re.match(r'^[IVX]+\.', line.strip()):
                formatted_lines.append(line)
            # Check if line is a subsection (letter or number)
            elif re.match(r'^\s+[A-Z]\.', line.strip()) or re.match(r'^\s+\d+\.', line.strip()):
                # Add extra indentation for subsections
                formatted_lines.append('    ' + line.strip())
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    def generate_table_of_contents(self) -> str:
        toc_prompt = """Create a professional Table of Contents for a strategic report comparing premium credit card offerings from KB Kookmin Bank and its competitors. The report is aimed at executive readers at KB Kookmin Bank, including the CFO.

Formatting requirements:
- Use Roman numerals for main sections
- Use capital letters for first-level subsections
- Use numbers for second-level subsections
- Maintain consistent indentation (main sections: no indentation, first-level: 4 spaces, second-level: 8 spaces)
- Ensure proper spacing between sections

The report should cover:
- Market context and competitive landscape
- Analysis of KB Kookmin Bank's premium credit card products
- Comparative analysis with competitors
- Strategic implications and recommendations
- References

Create a logical structure that builds from market context to specific analysis to strategic recommendations. Feel free to be creative with section titles while maintaining professionalism and clarity."""
        
        toc_response = self.generate_content(toc_prompt)
        toc_content = self.extract_content_between_markers(toc_response)
        return self.format_toc(toc_content)

    def paraphrase_content(self, content: str) -> str:
        paraphrase_prompt = f"""Please paraphrase the following content to make it more narrative, smooth, and connected. Ensure the writing flows naturally and maintains a professional, executive tone. Focus on improving transitions between sentences and paragraphs while preserving all key information and analysis:

{content}"""
        
        paraphrased_response = self.generate_content(paraphrase_prompt)
        return self.extract_content_between_markers(paraphrased_response)

    def generate_section_content(self, section_title: str, previous_sections: Optional[List[Dict]] = None) -> str:
        context = ""
        if previous_sections:
            context = "Previous sections have covered:\n" + "\n".join([f"- {section['title']}" for section in previous_sections])
        
        section_prompt = f"""{context}

Write a detailed, professional section for the following topic in our strategic report. The content should be comprehensive, analytical, and maintain a narrative flow.

Key requirements:
- Present data and comparisons in clear, organized tables where appropriate
- Use numbered citations in square brackets [1], [2], etc. for sources
- Ensure each citation corresponds to a reference in the References section
- Include citations for market data, product features, industry reports, and regulatory information
- Maintain a professional, executive tone
- Focus on strategic insights and actionable analysis

Section to write:
{section_title}"""
        
        section_response = self.generate_content(section_prompt)
        return self.extract_content_between_markers(section_response)

    def generate_references_section(self, report: List[Dict]) -> str:
        """Generate the references section based on citations found in the report"""
        # Extract all citations from the report
        citations = set()
        for section in report:
            citations.update(re.findall(r'\[(\d+)\]', section['content']))
        
        if not citations:
            return "No references cited in the report."
        
        # Generate references content
        references_prompt = f"""You are a financial research analyst. Generate a comprehensive References section for the report based on the following citation numbers: {sorted(citations)}.

For each citation, provide:
- Author(s) or organization name
- Title of the source
- Publication date
- Source type
- URL or publication details

Format each reference professionally and consistently. Ensure all references are from credible sources relevant to the credit card industry analysis."""
        
        references_response = self.generate_content(references_prompt)
        return self.extract_content_between_markers(references_response)

    def process_report(self, resume_from: Optional[str] = None) -> Tuple[List[Dict], str]:
        """Process the report, with optional resume functionality"""
        start_time = time.time()
        
        if resume_from:
            if not self.load_conversation_history(resume_from):
                self.logger.error(f"Could not resume from report {resume_from}")
                return [], ""
            self.current_report_id = resume_from
        else:
            # Reset conversation history for a new report
            self.conversation_history = []
            self.current_report_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate table of contents
        self.logger.info("Generating Table of Contents...")
        toc = self.generate_table_of_contents()
        self.logger.info("Table of Contents generated")
        
        # Extract sections from TOC using LLM
        sections = self.extract_sections_from_toc(toc)
        total_sections = len(sections)
        
        # Phase 1: Generate all sections
        self.logger.info("Phase 1: Generating all sections...")
        full_report = []
        for i, section in enumerate(sections, 1):
            self.logger.info(f"Generating section {i}/{total_sections}: {section.strip()}")
            
            # Calculate estimated time remaining
            elapsed_time = time.time() - start_time
            avg_time_per_section = elapsed_time / i if i > 0 else 0
            remaining_sections = total_sections - i
            estimated_remaining = avg_time_per_section * remaining_sections
            
            self.logger.info(f"Estimated time remaining: {estimated_remaining/60:.1f} minutes")
            
            # Generate content for the section with context of previous sections
            content = self.generate_section_content(section.strip(), full_report)
            
            full_report.append({
                'title': section.strip(),
                'content': content
            })
            
            self.logger.info(f"Completed section {i}/{total_sections}: {section.strip()}")
        
        # Generate references section
        self.logger.info("Generating References section...")
        references_content = self.generate_references_section(full_report)
        full_report.append({
            'title': 'References',
            'content': references_content
        })
        
        # Phase 2: Polish the entire report
        self.logger.info("Phase 2: Polishing the entire report...")
        polished_report = self.polish_entire_report(full_report)
        
        # Save to markdown file
        md_file, pdf_file = self.save_to_markdown(polished_report, toc)
        
        total_time = time.time() - start_time
        self.logger.info(f"Report generation completed in {total_time/60:.1f} minutes")
        
        return polished_report, md_file

    def polish_entire_report(self, report: List[Dict]) -> List[Dict]:
        """Polish each section to improve narrative flow and sentence transitions"""
        polished_report = []
        
        for section in report:
            polish_prompt = f"""Paraphrase the following section to improve narrative flow and sentence transitions. Focus on:
- Making sentences flow more smoothly
- Improving transitions between paragraphs
- Maintaining a professional tone
- Preserving all key information and analysis
- Keeping specialized terms and data unchanged

Section to paraphrase:
{section['content']}"""
            
            try:
                polished_response = self.generate_content(polish_prompt)
                polished_content = self.extract_content_between_markers(polished_response)
                
                polished_report.append({
                    'title': section['title'],
                    'content': polished_content
                })
                
                self.logger.info(f"Successfully polished section: {section['title']}")
                
            except Exception as e:
                self.logger.error(f"Error polishing section {section['title']}: {e}")
                # Keep original content if polishing fails
                polished_report.append(section)
        
        return polished_report

    def load_conversation_history(self, report_id: str) -> bool:
        """Load conversation history from a file"""
        history_file = Path(self.config['history_dir']) / f'conversation_{report_id}.json'
        
        if not Path(history_file).exists():
            return False
            
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            self.conversation_history = []
            for item in history_data:
                self.conversation_history.append(
                    types.Content(
                        role=item['role'],
                        parts=[types.Part.from_text(text=part) for part in item['parts']]
                    )
                )
            
            self.current_report_id = report_id
            self.logger.info(f"Loaded conversation history from {history_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error loading conversation history: {e}")
            return False

def main() -> None:
    """Main entry point for the report generator."""
    # Example configuration
    config = {
        'max_retries': 3,
        'retry_delay': 5,
        'temperature': 0.6,
        'top_p': 0.95,
        'max_output_tokens': 65535,
        'save_history': True,
        'history_dir': 'history',
        'reports_dir': 'reports',
        'log_level': logging.INFO,
    }
    
    generator = ReportGenerator(config)
    
    # To resume a previous report, uncomment and modify the following line:
    # report, filename = generator.process_report(resume_from="20240325_123456")
    
    # To start a new report:
    report, toc = generator.process_report()
    md_file, pdf_file = generator.save_to_markdown(report, toc)
    
    print(f"\nReport has been generated and saved to:")
    print(f"Markdown: {md_file}")
    print(f"PDF: {pdf_file}")


if __name__ == "__main__":
    main()