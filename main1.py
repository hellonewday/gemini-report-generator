import logging
from typing import List, Tuple, Dict, Any, Optional
from google.genai.types import Part
from config import REPORT_CONFIG as DEFAULT_REPORT_CONFIG
from report_generator.toc_generator import setup_client_and_tools, table_of_contents_prompt, extract_table_of_contents
from report_generator.section_generator import generate_section_content
from report_generator.content_polisher import polish_content
from report_generator.file_output import save_report_files
from report_generator.cloud_storage import upload_to_gcs
import csv
from utils import log_to_request_file
from datetime import datetime
import os
import socket
from os import getenv
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)
logger.propagate = True

class CustomFormatter(logging.Formatter):
    """Custom formatter that adds emojis based on log level."""
    def format(self, record):
        if not hasattr(record, 'emoji'):
            record.emoji = ''
        return super().format(record)

def setup_logging():
    """Setup logging with both console and file handlers."""
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomFormatter('%(asctime)s - %(emoji)s %(message)s', '%H:%M:%S'))
    logger.addHandler(console_handler)
    
    logger.setLevel(logging.INFO)

class ReportState:
    """Manages state for report generation."""
    def __init__(self):
        self.token_metrics = []
        self.contents = []
        self.report_references = []
        self.current_request_id = None
        self.LOGGING_CSV = "logging.csv"
        self.request_log_file = None
        self.config = None

def setup_request_logging(state: ReportState) -> None:
    """Setup request-specific logging file.
    
    Args:
        state: The report state object.
    """
    if not state.current_request_id:
        state.current_request_id = initialize_request()
    
    # Create system_log directory if it doesn't exist
    system_log_dir = "system_log"
    if not os.path.exists(system_log_dir):
        os.makedirs(system_log_dir)
    
    # Create request-specific log file in system_log directory
    state.request_log_file = os.path.join(system_log_dir, f"request_{state.current_request_id}.csv")
    headers = ["Timestamp", "Status", "Message"]
    
    try:
        with open(state.request_log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
    except Exception as e:
        logger.error(f"Error creating request log file: {str(e)}")

def log_request_status(state: ReportState, status: str, message: str) -> None:
    """Log status and message to request-specific CSV file and console.
    
    Args:
        state: The report state object.
        status: The current status of the request.
        message: The message to log.
    """
    if not state.request_log_file:
        setup_request_logging(state)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(state.request_log_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, status, message])
    except Exception as e:
        logger.error(f"Error writing to request log file: {str(e)}")
    
    # Map status to emoji
    status_emoji = {
        "initialize": "🚀",
        "generating": "💭",
        "polishing": "✨",
        "saving": "💾",
        "uploading": "📤",
        "url": "🌐",
        "completed": "✅",
        "error": "❌",
        "config": "⚙️",
        "info": "ℹ️",
        "metrics": "📊"
    }
    
    # Log to console with emoji
    emoji = status_emoji.get(status, "")
    logger.info(message, extra={'emoji': emoji})

def log_token_metrics(state: ReportState, response: 'GenerateContentResponse', section_name: str = "") -> None:
    """Log token usage metrics."""
    if not state.current_request_id:
        state.current_request_id = initialize_request()
        logger.warning("Request ID was not initialized. Initialized now.")
        
    input_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
    output_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
    model_name = response.model_version
    total_tokens = input_tokens + output_tokens
    
    cost_per_1m_input = 0.15 if "flash" in model_name.lower() else 1.25
    cost_per_1m_output = 3.5 if "flash" in model_name.lower() else 10.0
    
    input_cost = round(input_tokens * cost_per_1m_input / 1000000, 6)
    output_cost = round(output_tokens * cost_per_1m_output / 1000000, 6)
    total_cost = round(input_cost + output_cost, 6)
    
    metric = {
        "request_id": state.current_request_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "section": section_name,
        "model_version": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_per_1m_input": cost_per_1m_input,
        "cost_per_1m_output": cost_per_1m_output,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost
    }
    state.token_metrics.append(metric)
    
    # Log to CSV
    file_exists = os.path.isfile(state.LOGGING_CSV)
    headers = [
        "Request ID", "Timestamp", "Section", "Model Version", "Input Tokens",
        "Output Tokens", "Total Tokens", "Cost per 1M Input ($)", "Cost per 1M Output ($)",
        "Input Cost ($)", "Output Cost ($)", "Total Cost ($)"
    ]
    try:
        with open(state.LOGGING_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "Request ID": metric["request_id"],
                "Timestamp": metric["timestamp"],
                "Section": metric["section"],
                "Model Version": metric["model_version"],
                "Input Tokens": metric["input_tokens"],
                "Output Tokens": metric["output_tokens"],
                "Total Tokens": metric["total_tokens"],
                "Cost per 1M Input ($)": metric["cost_per_1m_input"],
                "Cost per 1M Output ($)": metric["cost_per_1m_output"],
                "Input Cost ($)": metric["input_cost"],
                "Output Cost ($)": metric["output_cost"],
                "Total Cost ($)": metric["total_cost"]
            })
    except Exception as e:
        msg = f"Error appending to logging CSV: {str(e)}"
        logger.error(msg)
        log_to_request_file(state.current_request_id, "error", msg)

def log_final_metrics(state: ReportState) -> None:
    """Log a summary of all token metrics."""
    if not state.token_metrics:
        return
        
    model_metrics = {}
    for metric in state.token_metrics:
        model = metric["model_version"]
        if model not in model_metrics:
            model_metrics[model] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "sections": []}
        model_metrics[model]["input_tokens"] += metric["input_tokens"]
        model_metrics[model]["output_tokens"] += metric["output_tokens"]
        model_metrics[model]["total_tokens"] += metric["total_tokens"]
        model_metrics[model]["sections"].append(metric)
    
    total_input = sum(m["input_tokens"] for m in state.token_metrics)
    total_output = sum(m["output_tokens"] for m in state.token_metrics)
    total_all = sum(m["total_tokens"] for m in state.token_metrics)
    total_cost = sum(m["total_cost"] for m in state.token_metrics)
    
    # Log to console
    logger.info("=" * 70)
    logger.info("📊 Overall Total Usage:")
    logger.info(f"   ├─ Total Input Tokens:  {total_input:,}")
    logger.info(f"   ├─ Total Output Tokens: {total_output:,}")
    logger.info(f"   └─ Total All Tokens:   {total_all:,}")
    logger.info(f"   └─ Total Cost:         ${total_cost:.6f}")
    logger.info("=" * 70)
    
    # Log to request file
    log_to_request_file(state.current_request_id, "metrics", "=" * 70)
    log_to_request_file(state.current_request_id, "metrics", "📊 Overall Total Usage:")
    log_to_request_file(state.current_request_id, "metrics", f"   ├─ Total Input Tokens:  {total_input:,}")
    log_to_request_file(state.current_request_id, "metrics", f"   ├─ Total Output Tokens: {total_output:,}")
    log_to_request_file(state.current_request_id, "metrics", f"   └─ Total All Tokens:   {total_all:,}")
    log_to_request_file(state.current_request_id, "metrics", f"   └─ Total Cost:         ${total_cost:.6f}")
    log_to_request_file(state.current_request_id, "metrics", "=" * 70)

def parse_table_of_contents(extracted_toc_text: str) -> Tuple[str, List[str]]:
    """Parse the extracted table of contents text.

    Args:
        extracted_toc_text: The text containing the TOC.

    Returns:
        Tuple[str, List[str]]: The report title and list of section titles.

    Raises:
        ValueError: If the TOC format is invalid.
    """
    parts = extracted_toc_text.split('SECTIONS:')
    if len(parts) != 2:
        raise ValueError("Invalid response format")
    title_line = parts[0].strip()
    title = title_line[6:].strip() if title_line.startswith('TITLE:') else "Premium Credit Card Market Analysis Report"
    sections = [line.strip() for line in parts[1].split('\n') if line.strip()]
    return title, sections

def get_system_prompt(config: Dict[str, Any]) -> str:
    localization_block = f"""
        - Eliminate translated-sounding phrases
        - Use native, idiomatic {config['language']} expressions suitable for C-level business readers
        - Remove hybrid or literal translation structures
        - Ensure cultural appropriateness in tone, phrasing, and examples
    """ if config['language'].lower() != 'english' else ""

    return f"""
        You are a senior financial analyst and native {config['language']}-speaking expert with 20+ years at {config['primary_bank']}. You specialize in credit card market analysis, competitive benchmarking, and product strategy. Your job is to write high-quality strategic reporting for executive stakeholders in the banking industry.

        **PRIMARY OBJECTIVE**
        Develop a comprehensive comparison of {config['credit_card_product_type']} products between {config['primary_bank']} and key competitors: {', '.join(config['comparison_banks'])}. Focus strictly on product features, pricing, benefits, and user-facing advantages.

        ---

        ## I. LANGUAGE & LOCALIZATION STANDARDS
        - All content must be in **{config['language']}** only (no mixed language or English notes)
        - Use formal {config['language']} business writing tone
        - Format numbers, dates, currency, and percentages in {config['language']} style
        - Write fluently and idiomatically for {config['language']}-speaking C-level readers
        {localization_block}
        - Do not mix regional data—focus **only** on the local market context
        - Ensure examples, sources, and data come **exclusively** from the local market

        ## II. CREDIT CARD PRODUCT COMPARISON SCOPE
        Direct comparison of:
        - Annual fees, interest rates, APR
        - Rewards program structure, cashback categories
        - Travel insurance, lounge access, and global perks
        - Sign-up bonuses, foreign transaction fees
        - Credit limits, eligibility criteria, mobile app functionality
        - Customer support features
        - Fee models, user experience, and differentiation points

        ## III. MARKET RESEARCH REQUIREMENTS
        - Use Google Search for **every major section**
        - Rely on **official bank websites**, product pages, and regulatory authorities
        - Cross-check all facts using **2–3 sources minimum**
        - Prioritize **recent, local**, and **verified** data only

        ## IV. ANALYTICAL DIMENSIONS
        - Focus on: {', '.join(config['analysis_focus'])}
        - Highlight implications for the local banking environment
        - Discuss strategic differentiation and customer impact

        ## V. PERFORMANCE METRICS TO TRACK
        - Card issuance and transaction volume
        - Revenue per card, retention rate
        - Market share by segment
        - Digital adoption rate
        - Source all metrics from official local institutions

        ## VI. TARGET MARKET SEGMENTS
        - Segments to focus on: {', '.join(config['market_segments'])}
        - Audience: {config['primary_bank']} Executive Team (CFO, Product Strategy, Marketing)
        - Emphasize: concrete product gaps, pricing strategy, and user benefits

        ## VII. COMPETITIVE BENCHMARKING
        - Compare with: {', '.join(config['comparison_banks'])}
        - Cover: product features, pricing structure, rewards, digital UX, customer support
        - Use side-by-side comparisons and product tables where applicable

        ## VIII. WRITING & FORMATTING STYLE
        - Executive-level tone: precise, data-driven, and actionable
        - Use markdown tables for comparison
        - Include charts, financial summaries, and strategic highlights
        - Avoid vague or high-level strategy—stay grounded in concrete product data

        ## IX. FINAL REMINDERS
        - Use **Google Search** actively and verify **every** data point
        - Use only **local market data**
        - Focus on **product-level comparisons**, not macroeconomic analysis
        - Ensure clarity, accuracy, and idiomatic {config['language']} writing throughout
        """


def initialize_request() -> str:
    """Initialize a new request with a unique ID and setup logging.
    
    Returns:
        str: The generated request ID.
    """
    request_id = f"{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8]}"
    
    # Create request log file
    log_file = f"request_{request_id}.csv"
    try:
        with open(log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Status", "Message"])
    except Exception as e:
        logger.error(f"Error creating request log file: {str(e)}")
    
    return request_id

def main(request_id: str = None, config: Optional[Dict[str, Any]] = None):
    """Orchestrate the report generation process.
    
    Args:
        request_id: Optional request ID. If not provided, a new one will be generated.
        config: Optional report configuration. If not provided, the default configuration will be used.
    """
    setup_logging()
    state = ReportState()
    
    if request_id is None:
        request_id = initialize_request()

    # Use provided config or fall back to default
    report_config = config or DEFAULT_REPORT_CONFIG.copy()  # Make a copy to avoid modifying the original
    
    # Check for orientation in environment variable
    env_orientation = os.environ.get("REPORT_ORIENTATION")
    if env_orientation:
        if env_orientation.lower() in ["landscape", "portrait"]:
            report_config["orientation"] = env_orientation.lower()
            logging.info(f"📄 Report orientation set from environment: {env_orientation}")
        else:
            logging.warning(f"⚠️ Invalid orientation in environment: {env_orientation}. Using default.")
    
    state.config = report_config
    
    state.current_request_id = request_id
    setup_request_logging(state)
    
    log_request_status(state, "initialize", "🚀 Starting report generation process...")
    log_request_status(state, "initialize", f"🚀 Request created: {request_id}")

    # Log configuration parameters
    log_request_status(state, "config", f"🧱 Scanning configuration parameters")
    log_request_status(state, "config", f"🌐 Report language: {report_config['language']}")
    log_request_status(state, "config", f"🏦 Your bank: {report_config['primary_bank']}")
    log_request_status(state, "config", f"🏢 You are comparing with: {', '.join(report_config['comparison_banks'])}")
    log_request_status(state, "config", f"📊 The report will focus on: {', '.join(report_config['analysis_focus'])}")
    log_request_status(state, "config", f"📈 The report will track these metrics: {', '.join(report_config['performance_metrics'])}")
    log_request_status(state, "config", f"👥 The report will be tailored to these market segments: {', '.join(report_config['market_segments'])}")
    log_request_status(state, "config", f"📋 The report will have these sections: {', '.join(report_config['report_sections'])}")
    log_request_status(state, "config", f"📏 Strict structure: {report_config['strict_structure']}")
    log_request_status(state, "config", f"🧪 Experimental mode: {report_config['demo_mode']}")
    log_request_status(state, "config", f"📄 Report orientation: {report_config.get('orientation', 'landscape')}")

    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    port = getenv('PORT', '8000')
    base_url = f"http://{ip_address}:{port}"
    log_request_status(state, "info", f"💲 You can view the cost metrics for this request at {base_url}/api/metrics/{request_id}")
    log_request_status(state, "info", f"ℹ️ To view the system log, please visit {base_url}/api/logs/{request_id}")
    
    # Setup
    client, google_search_tool = setup_client_and_tools()
    system_prompt = get_system_prompt(report_config)

    log_request_status(state, "generating", "💭 Report generation process started. This may take a while.")
    
    # Generate TOC
    log_request_status(state, "generating", "📋 Generating Table of Contents...")
    toc_prompt, toc_text, toc_response = table_of_contents_prompt(
        client, report_config['model_id'], state.contents, system_prompt, google_search_tool, state.current_request_id, report_config
    )
    log_token_metrics(state, toc_response, "Table of Contents Generation")
    
    _, extracted_toc_text, extracted_response = extract_table_of_contents(
        client, report_config['flash_model_id'], toc_prompt, toc_text, system_prompt, state.current_request_id, report_config
    )
    log_token_metrics(state, extracted_response, "Table of Contents Extraction")
    
    title, sections = parse_table_of_contents(extracted_toc_text)
    log_request_status(state, "generating", f"📑 Report Title: {title}")
    log_request_status(state, "generating", f"🔍 Extracted {len(sections)} sections: {', '.join(sections)}")

    # Generate sections
    sections_content = []
    sections_to_generate = [sections[1]] if report_config['demo_mode'] else sections
    for section_number, section_title in enumerate(sections_to_generate, 1):
        log_request_status(state, "generating", f"📝 Generating section {section_number}: {section_title}")
        content, section_references, response = generate_section_content(
            client, report_config['model_id'], section_title, section_number,
            state.contents, system_prompt, google_search_tool, state.current_request_id, report_config
        )
        log_token_metrics(state, response, f"Section {section_number}: {section_title}")
        
        log_request_status(state, "polishing", f"✨ Polishing section {section_number}: {section_title}")
        polished_content, polish_response = polish_content(
            client, report_config['flash_model_id'], content, system_prompt, state.current_request_id, report_config
        )
        log_token_metrics(state, polish_response, "Content Polishing")
        
        sections_content.append(polished_content)
        state.report_references.extend(section_references)
        log_request_status(state, "generating", f"✅ Section {section_number} completed: {section_title}")

    # Save files
    pdf_file = save_report_files(title, sections_content, state.report_references, state.current_request_id, report_config)
    
    # Upload to GCS
    public_url = upload_to_gcs(pdf_file, state.current_request_id, report_config)
    log_request_status(state, "url", f"🌐 Public URL: {public_url}");

    # Log final metrics
    log_final_metrics(state)
    log_request_status(state, "completed", "✅ Report generation process completed!")

if __name__ == "__main__":
    main(request_id="xxxxxtt")