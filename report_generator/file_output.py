import logging
import os
import platform
import pdfkit
import markdown
import re
from datetime import datetime
from markdown.extensions.toc import TocExtension
from utils import log_to_request_file
from typing import List, Dict, Any, Optional
from config import REPORT_CONFIG as DEFAULT_REPORT_CONFIG

logger = logging.getLogger(__name__)

def configure_pdfkit():
    """Configure pdfkit with the appropriate wkhtmltopdf path.

    Returns:
        pdfkit.configuration.Configuration: The configured pdfkit configuration.

    Raises:
        EnvironmentError: If wkhtmltopdf is not found or not executable.
    """
    config = pdfkit.configuration()
    if platform.system() == "Windows":
        wkhtmltopdf_path = os.environ.get(
            'WKHTMLTOPDF_PATH',
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )
        if os.path.exists(wkhtmltopdf_path):
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        else:
            msg = f"wkhtmltopdf not found at {wkhtmltopdf_path}. Please set WKHTMLTOPDF_PATH environment variable or install wkhtmltopdf."
            logger.error(msg)
            log_to_request_file(None, "error", msg)
            raise EnvironmentError("wkhtmltopdf not found on Windows")
    return config

def validate_orientation(orientation: str) -> str:
    """Validate the orientation value.
    
    Args:
        orientation: The orientation value to validate.
        
    Returns:
        str: The validated orientation value.
        
    Raises:
        ValueError: If the orientation value is invalid.
    """
    valid_orientations = ['landscape', 'portrait']
    if orientation.lower() not in valid_orientations:
        raise ValueError(f"Invalid orientation: {orientation}. Must be one of: {', '.join(valid_orientations)}")
    return orientation.lower()

def save_report_files(
    title: str,
    sections_content: List[str],
    references: List[str],
    request_id: str,
    config: Optional[Dict[str, Any]] = None
) -> str:
    """Save report files in various formats.

    Args:
        title: The report title.
        sections_content: List of section contents.
        references: List of references.
        request_id: The request ID.
        config: Optional configuration dictionary.

    Returns:
        str: The path to the generated PDF file.
    """
    # Use provided config or fall back to default
    report_config = config or DEFAULT_REPORT_CONFIG
    
    # Validate orientation
    try:
        orientation = validate_orientation(report_config.get('orientation', 'landscape'))
    except ValueError as e:
        error_msg = f"❌ {str(e)}. Defaulting to landscape."
        logger.error(error_msg)
        log_to_request_file(request_id, "error", error_msg)
        orientation = 'landscape'
    
    # Create output directory if it doesn't exist
    output_dir = "reports"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    language_dir = os.path.join(output_dir, report_config['language'].lower())
    if not os.path.exists(language_dir):
        os.makedirs(language_dir)
    
    # Create a filename based on report title and date
    title_slug = title.lower().replace(' ', '_')
    current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename_base = f"{title_slug}_{current_datetime}"
    
    log_to_request_file(request_id, "saving", f"💾 Saving report files with base name: {filename_base}")
    
    # Combine all sections into a single markdown file with table of contents
    markdown_content = f"# {title}\n\n[TOC]\n\n"
    for section in sections_content:
        markdown_content += section + "\n\n"
    
    # Add references section if references exist
    if references:
        markdown_content += "## References\n\n"
        for reference in references:
            markdown_content += reference + "\n\n"
    
    # Save Markdown file
    markdown_file = os.path.join(language_dir, f"{filename_base}.md")
    with open(markdown_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    # Convert Markdown to HTML with table of contents
    html_content = markdown.markdown(
        markdown_content,
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
    
    # Add section breaks before h2 headings
    html_content = re.sub(r'<h2', '<div class="section-break"></div><h2', html_content)
    
    # Select template based on orientation
    template_file = f"report_template{'_portrait' if orientation == 'portrait' else ''}.html"
    template_path = f'templates/{template_file}'
    
    # Load HTML template
    logger.info(f"Loading HTML template for {orientation} orientation: {template_path}")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
    except FileNotFoundError:
        msg = f"Template file '{template_path}' not found"
        logger.error(msg)
        log_to_request_file(request_id, "error", msg)
        # Fallback to a simple template
        template = """
        <!DOCTYPE html>
        <html lang="{{language}}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{title}}</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; }
                h1, h2, h3, h4 { color: #333; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .references-grid { margin: 1em 0; }
                .reference-item { padding: 8px; border: 1px solid #eee; }
            </style>
        </head>
        <body>
            {{content}}
        </body>
        </html>
        """
    
    # Replace placeholders with actual content
    template = template.replace('{', '{{').replace('}', '}}')   
    template = template.replace('{{content}}', '{content}')
    html_doc = template.format(content=html_content)
    
    reports_dir = 'reports'
    os.makedirs(reports_dir, exist_ok=True)
    base_filename = f"{current_datetime}_{request_id}_{report_config['language'].lower()}"

    md_file = os.path.join(reports_dir, f"{base_filename}.md")
    html_file = os.path.join(reports_dir, f"{base_filename}.html")
    pdf_file = os.path.join(reports_dir, f"{base_filename}.pdf")

    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    log_to_request_file(request_id, "saving", f"✅ Saved Markdown file: {md_file}")
        
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(template)
    log_to_request_file(request_id, "saving", f"✅ Saved HTML file: {html_file}")


    # Convert HTML to PDF using pdfkit
    try:
        pdf_options = {
            'page-size': 'A4',
            'orientation': orientation.capitalize(),  # Use the orientation from config
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': 'UTF-8',
            'no-outline': None,
            'enable-local-file-access': None,
            
            # Add footer with company text and page numbers
            'footer-right': '[page] / [topage]',
            'footer-font-size': '7',
            }
        
        pdfkit.from_string(html_doc, pdf_file, options=pdf_options)
        
        log_to_request_file(request_id, "saving", f"✅ Saved PDF file: {pdf_file}")
    except Exception as e:
        error_msg = f"❌ Error generating PDF: {str(e)}"
        logger.error(error_msg)
        log_to_request_file(request_id, "error", error_msg)
        # Return HTML file as fallback
        log_to_request_file(request_id, "saving", "🔄 Falling back to HTML output due to PDF generation failure")
        return html_file
    
    return pdf_file