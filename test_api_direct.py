import requests
import json
import time

# API endpoint
url = "http://localhost:8000/api/generate-report"

# Custom configuration
config = {
    "language": "Spanish",
    "analysis_focus": [
        "Market Positioning", 
        "Digital Transformation", 
        "Customer Experience"
    ],
    "performance_metrics": [
        "Digital Adoption Rate", 
        "Revenue per Card", 
        "Customer Satisfaction"
    ],
    "market_segments": [
        "High Net Worth", 
        "Young Professionals", 
        "Digital Natives"
    ],
    "report_sections": [
        "Executive Summary", 
        "Competitive Landscape", 
        "Digital Banking Features",
        "Customer Experience Analysis",
        "Strategic Recommendations"
    ],
    "strict_structure": True,
    "primary_bank": "Santander",
    "comparison_banks": ["BBVA", "CaixaBank", "Bankia"],
    "demo_mode": True,
    "writing_style": {
        "tone": "Professional",
        "formality_level": "High",
        "emphasis": ["Data-Driven Insights", "Strategic Recommendations"]
    }
}

# Make the request
print("Sending request to generate report with Spanish configuration...")
response = requests.post(
    url,
    json={"config": config}
)

# Check the response
print(f"Status Code: {response.status_code}")
print("Response:")
print(json.dumps(response.json(), indent=2))

# Get the request ID for checking logs and metrics
if response.status_code == 200:
    request_id = response.json().get("request_id")
    print(f"\nRequest ID: {request_id}")
    print(f"Check logs at: http://localhost:8000/api/logs/{request_id}")
    print(f"Check metrics at: http://localhost:8000/api/metrics/{request_id}")
    
    # Wait a bit for logs to be written
    print("\nWaiting for logs to be written...")
    time.sleep(3)
    
    # Check for configuration logs
    logs_url = f"http://localhost:8000/api/logs/{request_id}"
    logs_response = requests.get(logs_url)
    
    if logs_response.status_code == 200:
        logs = logs_response.json()
        config_logs = [log for log in logs if log.get("status") == "config"]
        
        if config_logs:
            print("\n⚙️ Configuration Logs:")
            for log in config_logs:
                print(f"  {log['message']}")
        
        # Show the first few general logs
        print("\nFirst few logs:")
        for log in logs[:10]:
            print(f"{log['timestamp']} [{log['status']}] {log['message']}")
    else:
        print(f"Error retrieving logs: {logs_response.text}") 