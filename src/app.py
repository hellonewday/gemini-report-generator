from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from gemini_report_generator.core.generator import ReportGenerator
from gemini_report_generator.core.models import ReportSection
from gemini_report_generator.config.defaults import DEFAULT_CONFIG
from gemini_report_generator.utils.logging import setup_logging

def main() -> None:
    """Main entry point for the report generator."""
    # Setup logging
    logger = setup_logging()
    logger.info("Starting report generation...")

    # Initialize the generator with default config
    generator = ReportGenerator()
    
    # Process the report
    report, toc = generator.process_report()
    
    # Save the report in multiple formats
    md_file, html_file, pdf_file = generator.save_to_markdown(report, toc)
    
    print(f"\nReport has been generated and saved to:")
    print(f"Markdown: {md_file}")
    print(f"HTML: {html_file}")
    print(f"PDF: {pdf_file}")

if __name__ == "__main__":
    main()