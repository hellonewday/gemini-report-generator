# Gemini Report Generator

A professional report generation system using Google's Gemini API to create detailed financial analysis reports.

## Features

- Generate professional financial reports
- Automatic Table of Contents generation
- Content paraphrasing for better narrative flow
- PDF export with professional styling
- Cross-platform compatibility (Windows/Linux)
- Conversation history tracking
- Configurable report generation

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/gemini-report-generator.git
cd gemini-report-generator
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install wkhtmltopdf:
- Windows: Download and install from https://wkhtmltopdf.org/downloads.html
- Linux (Ubuntu/Debian): `sudo apt-get install wkhtmltopdf`
- Linux (CentOS/RHEL): `sudo yum install wkhtmltopdf`

## Configuration

1. Create a `.env` file in the project root:
```env
GOOGLE_API_KEY=your_api_key_here
PROJECT_ID=your_project_id
LOCATION=your_location
```

2. Configure report settings in `config.yaml`:
```yaml
max_retries: 3
retry_delay: 5
temperature: 0.6
top_p: 0.95
max_output_tokens: 65535
save_history: true
history_dir: history
reports_dir: reports
log_level: INFO
```

## Usage

1. Basic usage:
```python
from gemini_report_generator import ReportGenerator

generator = ReportGenerator()
report, toc = generator.process_report()
```

2. With custom configuration:
```python
from gemini_report_generator import ReportGenerator

config = {
    'temperature': 0.7,
    'max_retries': 5,
    'save_history': True
}

generator = ReportGenerator(config)
report, toc = generator.process_report()
```

3. Resume a previous report:
```python
generator = ReportGenerator()
report, toc = generator.process_report(resume_from="20240325_123456")
```

## Project Structure

```
gemini-report-generator/
├── docs/                    # Documentation
├── src/                     # Source code
│   ├── __init__.py
│   ├── config.py           # Configuration handling
│   ├── generator.py        # Main report generator
│   ├── pdf.py             # PDF generation
│   ├── prompts.py         # Prompt templates
│   └── utils.py           # Utility functions
├── tests/                  # Test suite
│   ├── __init__.py
│   ├── test_generator.py
│   └── test_pdf.py
├── history/                # Conversation history
├── reports/               # Generated reports
├── .env                   # Environment variables
├── .gitignore
├── config.yaml           # Configuration file
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 