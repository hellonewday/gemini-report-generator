import logging
import os
import platform
import pdfkit
import markdown
import re
from datetime import datetime
from markdown.extensions.toc import TocExtension

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
            logger.error(
                "wkhtmltopdf not found at %s. Please set WKHTMLTOPDF_PATH environment variable "
                "or install wkhtmltopdf.", wkhtmltopdf_path
            )
            raise EnvironmentError("wkhtmltopdf not found on Windows")
    return config

def save_report_files(
    title: str,
    sections_content: list,
    report_references: list,
    current_request_id: str
) -> str:
    """Save report content to markdown, HTML, and PDF files.

    Args:
        title: The title of the report.
        sections_content: List of section content strings.
        report_references: List of reference strings.
        current_request_id: The unique request ID for the report.

    Returns:
        str: Path to the generated PDF file or HTML file if PDF generation fails.

    Raises:
        FileNotFoundError: If the HTML template file is missing.
    """
    # Create reports directory
    reports_dir = 'reports'
    os.makedirs(reports_dir, exist_ok=True)

    # Generate unique filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_filename = f"{timestamp}_{current_request_id}_korean"
    md_file = os.path.join(reports_dir, f"{base_filename}.md")
    html_file = os.path.join(reports_dir, f"{base_filename}.html")
    pdf_file = os.path.join(reports_dir, f"{base_filename}.pdf")

    # Combine content
    section_content = f"# {title}\n\n[TOC]\n\n" + "\n\n".join(sections_content) + "\n\n---\n## References\n\n" + "\n\n".join(report_references)

    # Save markdown
    logger.info("Saving content to markdown file...")
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(section_content)
    logger.info(f"Markdown file saved successfully: {md_file}")

    # Convert to HTML
    logger.info("Converting markdown to HTML...")
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
    html_content = re.sub(r'<h2', '<div class="section-break"></div><h2', html_content)

    # Read and process template
    logger.info("Loading HTML template...")
    try:
        with open('templates/report_template.html', 'r', encoding='utf-8') as f:
            template = f.read()
    except FileNotFoundError:
        logger.error("Template file 'report_template.html' not found")
        raise
    template = template.replace('{', '{{').replace('}', '}}').replace('{{content}}', '{content}')
    html_doc = template.format(content=html_content)

    # Save HTML
    logger.info("Saving HTML file...")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_doc)
    logger.info(f"HTML file saved successfully: {html_file}")

    # Generate PDF
    logger.info("Generating PDF...")
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
        path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        pdfkit.from_string(html_doc, pdf_file, options=pdf_options, configuration=config)

        logger.info(f"PDF generated successfully: {pdf_file}")
        return pdf_file
    except Exception as e:
        logger.error(f"Error in PDF generation: {str(e)}")
        logger.info("Falling back to HTML output due to PDF generation failure")
        return html_file