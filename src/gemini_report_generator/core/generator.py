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
from typing import Dict, List, Optional, Tuple, Any

import pdfkit
from google import genai
from google.genai import types
from markdown import markdown
from markdown.extensions.toc import TocExtension

from ..config.prompts import (
    format_system_instruction,
    format_table_of_contents,
    format_section_content,
    format_references_section,
    format_polish_content
)
from ..config.defaults import DEFAULT_CONFIG, DEFAULT_MARKERS, SKIP_PARAPHRASING_SECTIONS
from ..utils.file_handlers import (
    save_file, load_file, save_conversation_history,
    load_conversation_history, create_directories
)
from ..utils.logging import setup_logging
from .models import ReportSection

class ReportGenerator:
    """Main class for generating professional reports using Gemini API."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the ReportGenerator with configuration."""
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        
        self.client = genai.Client(
            vertexai=True,
            project=self.config['project_id'],
            location=self.config['location'],
        )
        self.model = self.config['model']
        self.system_instruction = self._get_system_instruction()
        
        self.conversation_history: List[types.Content] = []
        self.current_report_id: Optional[str] = None
        
        self.logger = setup_logging(self.config['log_level'])
        create_directories([self.config['history_dir'], self.config['reports_dir']])
        
        # Log the selected language
        language = self.config.get('language', 'English')
        self.logger.info(f"🌐 Selected language: {language}")

    def _get_system_instruction(self) -> str:
        """Get the system instruction for the Gemini model."""
        return format_system_instruction(
            primary_bank=self.config.get('primary_bank', 'Kookmin Bank'),
            language=self.config.get('language', 'English'),
            report_type=self.config.get('report_type', 'premium_credit_cards'),
            target_audience=self.config.get('target_audience', ['CFO', 'C-level executives']),
            writing_style=self.config.get('writing_style', {
                'tone': 'executive',
                'formality_level': 'high',
                'emphasis': ['strategic_insights', 'actionable_recommendations']
            }),
            analysis_focus=self.config.get('analysis_focus', [])
        )

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

    def generate_content(self, prompt: str, system_instruction: Optional[str] = None) -> str:
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
            save_conversation_history(serializable_history, history_file)
            self.logger.info(f"Saved conversation history to {history_file}")
        except Exception as e:
            self.logger.error(f"Error saving conversation history: {e}")

    def load_conversation_history(self, report_id: str) -> bool:
        """Load conversation history from a file."""
        history_file = Path(self.config['history_dir']) / f'conversation_{report_id}.json'
        
        if not Path(history_file).exists():
            return False
            
        try:
            history_data = load_conversation_history(history_file)
            if history_data is None:
                return False
                
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

    def generate_table_of_contents(self) -> str:
        """Generate and format the table of contents."""
        toc_prompt = format_table_of_contents(
            primary_bank=self.config.get('primary_bank', 'Kookmin Bank'),
            comparison_banks=self.config.get('comparison_banks', ['Hana', 'Woori', 'Shinhan Bank']),
            language=self.config.get('language', 'English'),
            report_type=self.config.get('report_type', 'premium_credit_cards'),
            target_audience=self.config.get('target_audience', ['CFO', 'C-level executives']),
            report_sections=self.config.get('report_sections', [])
        )
        toc_response = self.generate_content(toc_prompt)
        return self.extract_content_between_markers(toc_response)

    def generate_section_content(
        self,
        section_title: str,
        previous_sections: Optional[List[ReportSection]] = None,
        is_last_section: bool = False
    ) -> str:
        """Generate content for a specific section."""
        try:
            # Create context from previous sections
            context = ""
            if previous_sections:
                context = "\n".join([
                    f"- {section.title}: {section.content[:200]}..."  # Limit context length
                    for section in previous_sections[-3:]  # Only use last 3 sections for context
                ])
            
            # Check if this is the last section (References)
            if is_last_section:
                # Extract citations from previous sections
                citations = set()
                if previous_sections:
                    for section in previous_sections:
                        citations.update(re.findall(r'\[(\d+)\]', section.content))
                
                if not citations:
                    return f"## {section_title}\n\nNo references cited in the report."
                
                section_prompt = format_references_section(
                    context=context,
                    primary_bank=self.config.get('primary_bank', 'Kookmin Bank'),
                    citations=list(citations),
                    language=self.config.get('language', 'English')
                )
            else:
                section_prompt = format_section_content(
                    context=context,
                    section_title=section_title,
                    primary_bank=self.config.get('primary_bank', 'Kookmin Bank'),
                    language=self.config.get('language', 'English')
                )
            
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
        
        # Log each section title with its number
        self.logger.info("\n📋 Sections to be processed:")
        for idx, title in enumerate(section_titles, 1):
            self.logger.info(f"  {idx}. {title}")
        self.logger.info("")  # Add a blank line for readability
        
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
                    processed_sections,  # Pass previous sections for context
                    i == total_sections  # Pass is_last_section flag
                )
                
                # Skip polishing for specific sections or if it's the last section
                section_lower = section_title.lower()
                is_last_section = i == total_sections
                if any(skip_section in section_lower for skip_section in SKIP_PARAPHRASING_SECTIONS) or is_last_section:
                    processed_sections.append(ReportSection(
                        title=section_title,
                        content=content
                    ))
                    self.logger.info("⏭️ Skipping content polishing for this section")
                    continue
                else:
                    # Polish the content
                    self.logger.info("✨ Polishing content...")
                    polish_prompt = format_polish_content(content)
                    
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
        language = self.config.get('language', 'English')
        prompt = f"""
            Given the Table of Contents in {language} below, extract:
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
        pdf_filename = Path(self.config['reports_dir']) / f'{base_filename}.pdf'
        
        try:
            # Extract report title and sections from TOC
            report_title, _ = self.extract_sections_from_toc(toc)
            self.logger.info(f"\n📄 Saving report: {report_title}")
            
            # Generate markdown content
            md_content = self._generate_markdown_content(report_title, report)
            save_file(md_content, md_filename)
            
            # Generate and save HTML
            self.logger.info("🔄 Converting to HTML...")
            html_content = self._generate_html_content(md_content)
            save_file(self._get_html_template(html_content), html_filename)
            
            # Generate PDF
            self.logger.info("🔄 Converting to PDF...")
            try:
                pdfkit.from_file(
                    str(html_filename),
                    pdf_filename,
                    options=self._get_pdf_options(),
                    configuration=self._get_pdf_configuration()
                )
                self.logger.info(f"✅ PDF generated: {pdf_filename}")
            except Exception as e:
                self.logger.error(f"❌ Error generating PDF: {str(e)}")
                raise
            
            self._log_success(md_filename, html_filename, pdf_filename)
            return str(md_filename), str(html_filename), str(pdf_filename)
            
        except Exception as e:
            self.logger.error(f"❌ Error saving report: {str(e)}")
            raise

    def _get_pdf_configuration(self) -> pdfkit.configuration:
        """Get PDF configuration with proper path handling."""
        return pdfkit.configuration(wkhtmltopdf=self.config['wkhtmltopdf_path'])

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

    def _get_html_template(self, content: str) -> str:
        """Get the HTML template with embedded content."""
        template_path = Path(self.config['template_dir']) / 'report_template.html'
        try:
            template = load_file(template_path)
            if template is None:
                raise FileNotFoundError(f"Template file not found: {template_path}")
            # Double the curly braces in the CSS to escape them
            template = template.replace('{', '{{').replace('}', '}}')
            # Replace the content placeholder with a single set of braces
            template = template.replace('{{content}}', '{content}')
            # Add current date
            current_date = datetime.now().strftime("%B %d, %Y")
            return template.format(content=content, date=current_date)
        except Exception as e:
            self.logger.error(f"❌ Error loading HTML template: {str(e)}")
            raise

    def _generate_markdown_content(self, report_title: str, report: List[ReportSection]) -> str:
        """Generate markdown content from report sections."""
        md_content = f"# {report_title}\n\n[TOC]\n\n"
        
        for section in report:
            content_lines = section.content.split('\n')
            if content_lines:
                section_title = content_lines[0].strip()
                if section_title.startswith('#'):
                    section_content = '\n'.join(content_lines[1:]).strip()
                else:
                    section_content = section.content
            else:
                section_title = section.title
                section_content = section.content
            
            md_content += f"{section_title}\n\n"
            md_content += section_content
            md_content += "\n\n---\n\n"
        
        return md_content

    def _generate_html_content(self, md_content: str) -> str:
        """Generate HTML content from markdown."""
        return markdown(
            md_content,
            extensions=[
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
            ]
        )

    def _log_success(self, md_file: Path, html_file: Path, pdf_file: Path) -> None:
        """Log success messages for generated files."""
        self.logger.info("\n🎉 Report generation complete!")
        self.logger.info(f"📄 Markdown file: {md_file}")
        self.logger.info(f"🌐 HTML file: {html_file}")
        self.logger.info(f"📑 PDF file: {pdf_file}") 