import json
import os
import sys
from typing import Dict, Any
import requests
from pprint import pprint
import time

def test_api_with_custom_config():
    """Test the API with a custom configuration."""
    # Custom config for testing
    custom_config = {
        "language": "English",
        "analysis_focus": [
            "Market Share and Growth",
            "Revenue and Profitability",
            "Customer Acquisition Cost",
            "Customer Lifetime Value",
            "Digital Transformation Impact",
            "Competitive Positioning"
        ],
        "performance_metrics": [
            'Card Issuance Volume',
            'Transaction Volume',
            'Revenue per Card',
            'Customer Retention Rate',
            'Digital Adoption Rate',
            'Market Share by Segment'
        ],
        "market_segments": [
            "High Net Worth Individuals",
            "Business Professionals",
            "Digital-First Customers",
            "Loyalty Program Members"
        ],
        "report_sections": [
            'Executive Summary',
            'Premium Credit Card Product Comparison',
            'Pricing and Fee Analysis',
            'Rewards and Benefits Comparison',
            'Digital Features and Mobile Banking',
            'Customer Service and Support',
            'Market Performance Metrics',
            'Recommendations and Next Steps',
            "Conclusion"
        ],
        "strict_structure": False,
        "primary_bank": "Kookmin Bank",
        "comparison_banks": ["KEB Hana Bank", "Woori Bank", "Shinhan Bank"],
        "demo_mode": False,
        "credit_card_product_type": "Premium Credit Cards"
    }
    
    # API endpoint
    url = "http://localhost:8000/api/generate-report"
    
    # Make the request
    response = requests.post(
        url,
        json={"config": custom_config}
    )
    
    # Check the response
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("Response:")
        pprint(data)
        
        # Store the request ID for later use
        request_id = data.get("request_id")
        print(f"\nRequest ID: {request_id}")
        print(f"You can check the logs at: http://localhost:8000/api/logs/{request_id}")
        print(f"You can check the metrics at: http://localhost:8000/api/metrics/{request_id}")
        
        return request_id
    else:
        print(f"Error: {response.text}")
        return None

def check_config_logs(request_id):
    """Check the request logs for configuration information."""
    print("\nChecking for configuration logs...")
    
    # Wait a bit to ensure logs are written
    time.sleep(2)
    
    # API endpoint
    url = f"http://localhost:8000/api/logs/{request_id}"
    
    # Make the request
    response = requests.get(url)
    
    # Check the response
    if response.status_code == 200:
        logs = response.json()
        
        # Look for configuration logs
        config_logs = [log for log in logs if log.get("status") == "config"]
        
        if config_logs:
            print("\n⚙️ Configuration Logs:")
            for log in config_logs:
                print(f"  {log['message']}")
        else:
            print("No configuration logs found.")
    else:
        print(f"Error retrieving logs: {response.text}")

def test_validation_errors():
    """Test validation errors for missing required fields."""
    print("\nTesting validation errors...\n")
    
    # Missing required fields
    invalid_config = {
        "language": "English",
        # Missing analysis_focus
        "performance_metrics": [
            "Card Issuance Volume"
        ],
        # Missing market_segments
        "report_sections": [
            "Executive Summary"
        ],
        "strict_structure": True,
        "primary_bank": "Chase Bank",
        # Missing comparison_banks
        "demo_mode": True
    }
    
    # API endpoint
    url = "http://localhost:8000/api/generate-report"
    
    # Make the request
    response = requests.post(
        url,
        json={"config": invalid_config}
    )
    
    # Check the response
    print(f"Status code: {response.status_code}")
    print("Response:")
    pprint(response.json())

if __name__ == "__main__":
    print("Testing API with custom configuration...")
    request_id = test_api_with_custom_config()
    
    if request_id:
        # Check configuration logs
        check_config_logs(request_id)
        
        # Wait a bit more time for processing to continue
        time.sleep(5)
        
        # Check initial logs
        print("\nChecking initial logs...")
        logs_url = f"http://localhost:8000/api/logs/{request_id}"
        logs_response = requests.get(logs_url)
        if logs_response.status_code == 200:
            logs = logs_response.json()
            print(f"Found {len(logs)} log entries.")
            print("First 15 log entries:")
            for log in logs[:15]:  # Show first 15 logs
                print(f"{log['timestamp']} [{log['status']}] {log['message']}")
        
        # Test validation errors
        test_validation_errors()
    
    print("\nTests completed")