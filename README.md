# Gemini Report Generator

A sophisticated report generation system that leverages Google's Gemini AI to create comprehensive financial analysis reports, specifically focused on credit card products and market analysis.

## Overview

This system generates detailed financial reports by utilizing Google's Gemini AI models to analyze and compare credit card products across major banks. It's designed to produce executive-level reports with a focus on strategic insights and competitive analysis.

## Configuration

The system is highly configurable through the `REPORT_CONFIG` dictionary. Here are the key configuration parameters:

### Core Business Parameters
```python
'primary_bank': 'Kookmin Bank',
'comparison_banks': ['Hana', 'Woori', 'Shinhan Bank'],
'report_type': 'Premium Credit Cards',
'time_period': '2024 Q1',
'language': 'English'  # Supports multiple languages
```

### Analysis Focus
Configures the key areas of analysis in the report:
```python
'analysis_focus': [
    'Market Share and Growth',
    'Revenue and Profitability',
    'Customer Acquisition Cost',
    'Customer Lifetime Value',
    'Digital Transformation Impact',
    'Competitive Positioning'
]
```

### Performance Metrics
Defines the specific metrics to track and analyze:
```python
'performance_metrics': [
    'Card Issuance Volume',
    'Transaction Volume',
    'Revenue per Card',
    'Customer Retention Rate',
    'Digital Adoption Rate',
    'Market Share by Segment'
]
```

### Market Segments
Specifies the target market segments for analysis:
```python
'market_segments': [
    'High Net Worth Individuals',
    'Business Professionals',
    'Digital-First Customers',
    'Loyalty Program Members'
]
```

### Report Structure
Controls the structure of the generated report:
```python
'report_sections': [
    'Executive Summary',
    'Market Performance Analysis',
    'Competitive Landscape',
    'Strategic Opportunities',
    'Risk Assessment',
    'Actionable Recommendations'
]
```

### Structure Mode
Controls whether the report structure is flexible or strict:
```python
'strict_structure': False  # Set to True to enforce exact report structure
```

### Writing Style
Configures the tone and style of the report:
```python
'writing_style': {
    'tone': 'Executive and Strategic',
    'formality_level': 'High',
    'emphasis': ['Data-Driven Insights', 'Strategic Implications', 'ROI Impact']
}
```

## Implementation Details

### AI Model Configuration
- Uses Google's Gemini AI models:
  - Primary model: `gemini-2.5-pro-preview-05-06`
  - Flash model: `gemini-2.5-flash-preview-04-17`
- Temperature setting: 0.4 (for balanced creativity and consistency)
- Maximum output tokens: 65535

### Report Generation Process
1. **Table of Contents Generation**
   - Creates a structured outline based on configuration
   - Respects strict/flexible structure mode
   - Excludes References and Appendices sections

2. **Content Generation**
   - Uses Google Search for real-time data verification
   - Implements retry mechanism with exponential backoff
   - Maintains consistent language and formatting

3. **Output Formats**
   - Generates reports in multiple formats:
     - Markdown (.md)
     - HTML (.html)
     - PDF (.pdf)

### Error Handling
- Implements retry mechanism with exponential backoff
- Maximum retries: 3
- Initial delay: 1 second
- Maximum delay: 10 seconds

### Logging and Metrics
- Tracks token usage and costs
- Logs generation progress and errors
- Maintains detailed metrics in CSV format

## Usage

1. Configure the `REPORT_CONFIG` dictionary with desired parameters
2. Run the script:
```bash
python test.py
```

3. Generated reports will be available in:
   - `section_content.md`
   - `section_content.html`
   - `section_content.pdf`

## Dependencies
- google-generativeai
- markdown
- pdfkit
- wkhtmltopdf (for PDF generation)

## Notes
- Ensure proper API credentials are configured for Google's Gemini AI
- PDF generation requires wkhtmltopdf to be installed and configured
- The system supports multiple languages but defaults to English

Copyright © 2024 SmartOSC AI Team. All rights reserved.

## Features

- Generate professional financial reports using Google's Gemini API
- Support for multiple languages and cultural contexts
- Automatic table of contents generation
- Section-by-section content generation with context awareness
- Content polishing and refinement
- Multiple output formats (Markdown, HTML, PDF)
- Conversation history tracking and resumption
- Comprehensive logging with emoji support
- Configurable report structure and styling

## Installation

1. Clone the repository:
```bash
git clone https://github.com/smartosc-ai/gemini-report-generator.git
cd gemini-report-generator
```

2. Install the package:
```bash
pip install -e .
```

3. Install wkhtmltopdf (required for PDF generation):
- Windows: Download and install from [wkhtmltopdf website](https://wkhtmltopdf.org/downloads.html)
- Linux: `sudo apt-get install wkhtmltopdf`
- macOS: `brew install wkhtmltopdf`

4. Set up environment variables:
```bash
# Create a .env file
cp .env.example .env

# Edit .env with your Google Cloud credentials
```

## Project Structure

```
gemini-report-generator/
├── src/
│   └── gemini_report_generator/
│       ├── __init__.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── defaults.py
│       │   └── prompts.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── generator.py
│       │   └── models.py
│       └── utils/
│           ├── __init__.py
│           ├── file_handlers.py
│           └── logging.py
├── templates/
│   └── report_template.html
├── tests/
├── .env.example
├── .gitignore
├── README.md
└── setup.py
```

## Configuration

The generator can be configured through the following parameters:

- `language`: Report language (default: 'English')
- `primary_bank`: Target bank for analysis
- `comparison_banks`: List of banks to compare against
- `report_type`: Type of financial product being analyzed
- `target_audience`: List of target audience roles
- `analysis_focus`: Key areas to focus on in the analysis
- `report_sections`: Customizable report structure
- `writing_style`: Writing style parameters

## Development

### Prerequisites

- Python 3.8 or higher
- Google Cloud account with Gemini API access
- wkhtmltopdf for PDF generation

### Setup Development Environment

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

2. Install development dependencies:
```bash
pip install -e ".[dev]"
```

3. Install pre-commit hooks:
```bash
pre-commit install
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
black .

# Sort imports
isort .

# Type checking
mypy .

# Linting
flake8
```

## License

This project is proprietary software. All rights reserved.

## Acknowledgments

- Google Gemini API for the AI capabilities
- wkhtmltopdf for PDF generation
- Python-Markdown for markdown processing 