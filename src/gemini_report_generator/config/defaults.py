import logging
import os
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    'max_retries': 3,
    'retry_delay': 5,
    'temperature': 0.3,
    'top_p': 0.95,
    'max_output_tokens': 65535,
    'save_history': True,
    'history_dir': 'history',
    'reports_dir': 'reports',
    'log_level': logging.INFO,
    'model': "gemini-2.5-pro-preview-05-06",
    'project_id': "nth-droplet-458903-p4",
    'location': "us-central1",
    'wkhtmltopdf_path': os.getenv('WKHTMLTOPDF_PATH', r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"),
    'template_dir': 'templates',
    'language': 'Korean',  # Default language
    'primary_bank': 'Kookmin Bank',  # Primary target bank
    'comparison_banks': ['Hana', 'Woori', 'Shinhan Bank'],  # Banks to compare against
    
    # Business-specific parameters
    'report_type': 'Premium Credit Cards',  # Type of financial product being analyzed
    'target_audience': ['Chief Financial Officer', 'Executive Leadership Team'],  # Target audience for the report
    'analysis_focus': [  # Key areas to focus on in the analysis
        'Product Features and Benefits',
        'Fee Structure and Pricing',
        'Rewards and Loyalty Programs',
        'Digital Banking Experience',
        'Target Customer Segments',
        'Market Differentiation'
    ],
    'report_sections': [  # Customizable report structure
        'Market Overview and Dynamics',
        'Primary Bank Product Analysis',
        'Competitive Landscape Analysis',
        'Strategic Insights and Trends',
        'Strategic Recommendations',
        'References'
    ],
    'writing_style': {  # Customizable writing style parameters
        'tone': 'Executive and Professional',
        'formality_level': 'High',
        'emphasis': ['Strategic Insights', 'Actionable Recommendations']
    }
}

# Constants for content markers
DEFAULT_MARKERS = {
    'primary': ("\n\n***\n\n", "\n\n***\n\n"),
    'secondary': ("\n\n---\n\n", "\n\n---\n\n")
}

# Sections that should skip content polishing
SKIP_PARAPHRASING_SECTIONS = ['appendix', 'appendices', 'references'] 