# Gemini Report Generator

A professional report generation system using Google's Gemini API to create detailed financial analysis reports.

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

## Usage

Basic usage:

```python
from gemini_report_generator.core.generator import ReportGenerator

# Initialize the generator
generator = ReportGenerator()

# Generate a report
report, toc = generator.process_report()

# Save the report in multiple formats
md_file, html_file, pdf_file = generator.save_to_markdown(report, toc)
```

Custom configuration:

```python
config = {
    'language': 'Korean',
    'primary_bank': 'Kookmin Bank',
    'comparison_banks': ['Hana', 'Woori', 'Shinhan Bank'],
    'report_type': 'Premium Credit Cards',
    'target_audience': ['CFO', 'C-level executives'],
}

generator = ReportGenerator(config=config)
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