import logging
from typing import List, Tuple
from google.genai.types import Part
from config import REPORT_CONFIG
from utils import initialize_request
from report_generator.toc_generator import setup_client_and_tools, table_of_contents_prompt, extract_table_of_contents
from report_generator.section_generator import generate_section_content
from report_generator.content_polisher import polish_content
from report_generator.file_output import save_report_files
from report_generator.cloud_storage import upload_to_gcs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class ReportState:
    """Manages state for report generation."""
    def __init__(self):
        self.token_metrics = []
        self.contents = []
        self.report_references = []
        self.current_request_id = None
        self.LOGGING_CSV = "logging.csv"

def log_token_metrics(state: ReportState, response: 'GenerateContentResponse', section_name: str = "") -> None:
    """Log token usage metrics.

    Args:
        state: The report state object.
        response: The response object from content generation.
        section_name: The name of the section being logged.
    """
    if not state.current_request_id:
        state.current_request_id = initialize_request()
        logger.warning("Request ID was not initialized. Initialized now.")
        
    input_tokens = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count
    model_name = response.model_version
    total_tokens = input_tokens + output_tokens
    
    cost_per_1m_input = 0.15 if "flash" in model_name.lower() else 1.25
    cost_per_1m_output = 3.5 if "flash" in model_name.lower() else 10.0
    
    input_cost = round(input_tokens * cost_per_1m_input / 1000000, 6)
    output_cost = round(output_tokens * cost_per_1m_output / 1000000, 6)
    total_cost = round(input_cost + output_cost, 6)
    
    metric = {
        "request_id": state.current_request_id,
        "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
    
    import csv
    import os
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
        logger.error(f"Error appending to logging CSV: {str(e)}")

def log_final_metrics(state: ReportState) -> None:
    """Log a summary of all token metrics.

    Args:
        state: The report state object.
    """
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
    
    logger.info("=" * 70)
    logger.info("Overall Total Usage:")
    logger.info(f"   Total Input Tokens: {total_input:,}")
    logger.info(f"   Total Output Tokens: {total_output:,}")
    logger.info(f"   Total All Tokens: {total_all:,}")
    logger.info(f"   Total Cost: ${total_cost:.6f}")
    logger.info("=" * 70)

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

def get_system_prompt() -> str:
    """Generate the system prompt for the report.

    Returns:
        str: The system prompt string.
    """
    return f"""
        You are a senior {REPORT_CONFIG['language']} financial analyst specializing in credit card products with 20 years of experience at {REPORT_CONFIG['primary_bank']}. Your expertise spans credit card market analysis, product comparison, and competitive intelligence.
        **PRIMARY OBJECTIVE:**
        Create a comprehensive comparison of premium credit card products between {REPORT_CONFIG['primary_bank']} and its key competitors ({', '.join(REPORT_CONFIG['comparison_banks'])}), focusing on concrete product features, pricing, and benefits that drive customer decisions.
        **CRITICAL REQUIREMENTS:**
        1. LANGUAGE AND LOCALIZATION:
        - ALL content MUST be in {REPORT_CONFIG['language']} with no explanation in other languages
        - Use formal {REPORT_CONFIG['language']} business language
        - Format numbers, dates, currency, and percentages in {REPORT_CONFIG['language']}
        - Focus EXCLUSIVELY on the local market context and data
        - Do not mix data or information from different regions
        - Ensure all market data, statistics, and examples are from the local market only
        - Verify that all sources and references are from the local market
        2. CREDIT CARD COMPARISON FOCUS:
        - Detailed analysis of specific credit card products and their features
        - Direct comparison of:
            - Annual fees and charges
            - Interest rates and APR
            - Rewards programs and points structure
            - Cashback rates and categories
            - Travel benefits and insurance coverage
            - Welcome bonuses and sign-up offers
            - Foreign transaction fees
            - Credit limits and eligibility criteria
        - Clear presentation of pricing models and fee structures
        - Concrete benefits and value propositions
        - Digital features and mobile app capabilities
        - Customer service and support options
        3. RESEARCH:
        - MUST use Google Search for EVERY section
        - Verify all information with multiple sources
        - Focus on official bank websites and product pages
        - Ensure data is current and accurate
        - Prioritize local market sources and data
        - Cross-reference information with local regulatory bodies and financial institutions
        - Exclude any data or information from other regions
        4. ANALYSIS FOCUS:
        The analysis must cover these key areas:
        - Product feature comparison
        - Pricing and fee analysis
        - Benefits and rewards comparison
        - Digital capabilities
        - Customer service offerings
        - Market positioning based on concrete features
        - All analysis must be grounded in local market context
        5. KEY PERFORMANCE METRICS:
        Track and analyze these specific metrics:
        - Card issuance volume
        - Transaction volume
        - Revenue per card
        - Customer retention rate
        - Digital adoption rate
        - Market share by segment
        - All metrics must be from local market sources
        6. TARGET MARKET SEGMENTS:
        Focus analysis on these key segments:
        {', '.join(REPORT_CONFIG['market_segments'])}
        - Primary: {REPORT_CONFIG['primary_bank']} Executive Team
        - Focus on concrete product comparisons
        - Emphasis on pricing and features
        - Clear value propositions
        - Direct competitive advantages
        - All segment analysis must be based on local market data
        7. COMPETITIVE ANALYSIS:
        - Comparison banks: {', '.join(REPORT_CONFIG['comparison_banks'])}
        - Direct product feature comparison
        - Pricing strategy analysis
        - Benefits and rewards comparison
        - Digital capabilities
        - Customer experience
        - All competitive analysis must be within the local market context
        8. REPORT STRUCTURE:
        {"Follow this exact section structure:" if REPORT_CONFIG['strict_structure'] else "Following this report structure as a suggestion for the report, but you can change the structure if needed to provide strong and clear analysis."}
        {', '.join(REPORT_CONFIG['report_sections'])}
        9. WRITING STYLE:
        - Tone: {REPORT_CONFIG['writing_style']['tone']}
        - Formality: {REPORT_CONFIG['writing_style']['formality_level']}
        - Emphasis: {', '.join(REPORT_CONFIG['writing_style']['emphasis'])}
        - Clear executive summary
        - Actionable insights
        - Data visualization
        **FINAL REMINDER:**
        You MUST use Google Search for EVERY main section and ensure ALL content is in {REPORT_CONFIG['language']}. Focus on providing detailed credit card product comparisons with concrete features, pricing, and benefits that would be valuable for {REPORT_CONFIG['language']}-speaking banking executives. Avoid abstract strategic analysis and focus on actionable, concrete product comparisons. Most importantly, ensure ALL data, examples, and market information are from the local market only - do not mix data from different regions.
    """

def main():
    """Orchestrate the report generation process."""
    logger.info("Starting report generation process...")
    state = ReportState()
    state.current_request_id = initialize_request()
    
    # Setup
    client, google_search_tool = setup_client_and_tools()
    system_prompt = get_system_prompt()

    # Generate TOC
    toc_prompt, toc_text, toc_response =  table_of_contents_prompt(
        client, REPORT_CONFIG['model_id'], state.contents, system_prompt, google_search_tool
    )
    log_token_metrics(state, toc_response, "Table of Contents Generation")
    extracted_toc_prompt, extracted_toc_text, extracted_response =  extract_table_of_contents(
        client, REPORT_CONFIG['flash_model_id'], toc_prompt, toc_text, system_prompt
    )
    log_token_metrics(state, extracted_response, "Table of Contents Extraction")
    title, sections = parse_table_of_contents(extracted_toc_text)
    logger.info(f"Report Title: {title}")
    logger.info(f"Found {len(sections)} sections to process")

    # Generate sections
    sections_content = []
    sections_to_generate = [sections[1]] if REPORT_CONFIG['demo_mode'] else sections
    for section_number, section_title in enumerate(sections_to_generate, 1):
        content, section_references, response =  generate_section_content(
            client, REPORT_CONFIG['model_id'], section_title, section_number,
            state.contents, system_prompt, google_search_tool
        )
        log_token_metrics(state, response, f"Section {section_number}: {section_title}")
        polished_content, polish_response = polish_content(
            client, REPORT_CONFIG['flash_model_id'], content, system_prompt
        )
        log_token_metrics(state, polish_response, "Content Polishing")
        sections_content.append(polished_content)
        state.report_references.extend(section_references)
        logger.info(f"Section {section_number} completed: {section_title}")

    # Save files
    pdf_file = save_report_files(title, sections_content, state.report_references, state.current_request_id)
    
    # Upload to GCS
    upload_to_gcs(pdf_file, state.current_request_id)
    
    # Log final metrics
    log_final_metrics(state)
    logger.info("Report generation process completed!")

if __name__ == "__main__":
    main()