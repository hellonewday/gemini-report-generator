import logging
import os
import markdown
import re
import pdfkit
from datetime import datetime
from markdown.extensions.toc import TocExtension
from config import REPORT_CONFIG

logger = logging.getLogger(__name__)

def save_report_files(title, sections_content, report_references, current_request_id):
    """Save report content to markdown, HTML, and PDF files."""
    # Create reports directory
    reports_dir = 'reports'
    os.makedirs(reports_dir, exist_ok=True)

    # Generate unique filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_filename = f"{timestamp}_{current_request_id}_{REPORT_CONFIG['language'].lower()}"
    md_file = os.path.join(reports_dir, f"{base_filename}.md")
    html_file = os.path.join(reports_dir, f"{base_filename}.html")
    pdf_file = os.path.join(reports_dir, f"{base_filename}.pdf")

    # Combine content
    section_content = f"# {title}\n\n[TOC]\n\n" + "\n\n".join(sections_content) + "\n\n---\n## References\n\n" + "\n\n".join(report_references)

    # Save markdown
    logger.info("💾 Saving content to markdown file...")
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(section_content)
    logger.info(f"✅ Markdown file saved successfully: {md_file}")

    # Convert to HTML
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
    html_content = re.sub(r'<h2', '<div class="section-break"></div><h2', html_content)

    # Read and process template
    logger.info("📄 Processing HTML template...")
    with open('templates/report_template.html', 'r', encoding='utf-8') as f:
        template = f.read()
    template = template.replace('{', '{{').replace('}', '}}').replace('{{content}}', '{content}')
    html_doc = template.format(content=html_content)

    # Save HTML
    logger.info("💾 Saving HTML file...")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_doc)
    logger.info(f"✅ HTML file saved successfully: {html_file}")

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
        pdfkit.from_string(html_doc, pdf_file, options=pdf_options)
        logger.info(f"✅ PDF generated successfully: {pdf_file}")
    except Exception as e:
        logger.error(f"❌ Error in PDF generation: {str(e)}")
        raise

    return pdf_file