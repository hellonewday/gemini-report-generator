#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Testing the report generator API with custom configuration${NC}"
echo -e "${BLUE}Sending POST request to generate a report...${NC}"

# Store the response in a variable
RESPONSE=$(curl -s -X POST http://localhost:8000/api/generate-report \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "language": "French",
      "analysis_focus": ["Market Share", "Profitability Analysis", "Customer Engagement"],
      "performance_metrics": ["Transaction Volume", "Customer Retention Rate", "Average Spend"],
      "market_segments": ["Premium Customers", "Business Accounts", "Student Accounts"],
      "report_sections": ["Executive Summary", "Competitive Analysis", "Performance Metrics"],
      "strict_structure": false,
      "primary_bank": "BNP Paribas",
      "comparison_banks": ["Société Générale", "Crédit Agricole", "BPCE"],
      "demo_mode": true,
      "writing_style": {
        "tone": "Professional and Analytical",
        "formality_level": "High",
        "emphasis": ["Data-Driven Insights", "Strategic Recommendations"]
      }
    }
  }')

# Parse the request_id from the response
REQUEST_ID=$(echo $RESPONSE | grep -o '"request_id":"[^"]*' | sed 's/"request_id":"//')

echo -e "${GREEN}Response:${NC}"
echo $RESPONSE | python -m json.tool

if [ -n "$REQUEST_ID" ]; then
  echo -e "\n${YELLOW}Request ID: $REQUEST_ID${NC}"
  echo -e "Check logs at: http://localhost:8000/api/logs/$REQUEST_ID"
  echo -e "Check metrics at: http://localhost:8000/api/metrics/$REQUEST_ID"
  
  # Wait a bit for logs to be generated
  echo -e "\n${BLUE}Waiting for logs to be generated (3 seconds)...${NC}"
  sleep 3
  
  # Get the logs
  echo -e "\n${GREEN}Fetching logs:${NC}"
  curl -s "http://localhost:8000/api/logs/$REQUEST_ID" | python -m json.tool
else
  echo -e "${YELLOW}No request ID found in the response.${NC}"
fi

# Example of testing validation errors
echo -e "\n\n${GREEN}Testing validation errors with missing required fields${NC}"
echo -e "${BLUE}Sending POST request with invalid configuration...${NC}"

curl -s -X POST http://localhost:8000/api/generate-report \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "language": "German",
      "performance_metrics": ["Transaction Volume"],
      "report_sections": ["Executive Summary"],
      "strict_structure": true,
      "primary_bank": "Deutsche Bank",
      "demo_mode": true
    }
  }' | python -m json.tool 