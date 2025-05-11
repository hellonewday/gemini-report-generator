from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from datetime import datetime
import uuid
import threading
import csv
import os
from typing import List, Dict, Optional
from main1 import main
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pydantic import BaseModel, Field, validator

app = FastAPI()

## CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for report configuration
class WritingStyle(BaseModel):
    tone: str
    formality_level: str
    emphasis: List[str]

class ReportConfig(BaseModel):
    language: str
    analysis_focus: List[str]
    performance_metrics: List[str]
    market_segments: List[str]
    report_sections: List[str]
    strict_structure: bool
    primary_bank: str
    comparison_banks: List[str]
    demo_mode: bool
    orientation: Optional[str] = "landscape"  # Report orientation - can be 'landscape' or 'portrait'
    credit_card_product_type: Optional[str] = "Premium Credit Cards"
    writing_style: Optional[WritingStyle] = None
    model_id: Optional[str] = "gemini-2.5-pro-preview-05-06"
    flash_model_id: Optional[str] = "gemini-2.5-flash-preview-04-17"
    safety_settings: Optional[List[Dict]] = None

    @validator('orientation')
    def validate_orientation(cls, v):
        valid_orientations = ['landscape', 'portrait']
        if v.lower() not in valid_orientations:
            raise ValueError(f"Orientation must be one of: {', '.join(valid_orientations)}")
        return v.lower()

    @validator('comparison_banks')
    def validate_comparison_banks(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one comparison bank must be provided')
        return v

    @validator('language', 'primary_bank')
    def validate_non_empty_string(cls, v):
        if not v or v.strip() == "":
            raise ValueError('Field cannot be empty')
        return v

    @validator('analysis_focus', 'performance_metrics', 'market_segments', 'report_sections')
    def validate_non_empty_list(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one item must be provided')
        return v

# Pydantic models for statistics endpoint
class CostOverview(BaseModel):
    total_cost: float
    cost_by_model: Dict[str, float]
    cost_trend: Dict[str, float]  # Daily cost trend

class TokenUsage(BaseModel):
    total_tokens: int
    input_tokens: int
    output_tokens: int
    tokens_by_model: Dict[str, int]

class RequestVolume(BaseModel):
    total_requests: int
    requests_by_model: Dict[str, int]
    requests_over_time: Dict[str, int]  # Daily request count

class ModelUsage(BaseModel):
    requests_by_model: Dict[str, int]
    avg_tokens_per_request: Dict[str, float]
    avg_cost_per_request: Dict[str, float]

class HighImpactRequests(BaseModel):
    top_cost_requests: List[Dict]
    top_token_requests: List[Dict]

class StatisticsResponse(BaseModel):
    cost_overview: CostOverview
    token_usage: TokenUsage
    request_volume: RequestVolume
    model_usage: ModelUsage
    high_impact_requests: HighImpactRequests

class ReportGenerationRequest(BaseModel):
    config: ReportConfig

def run_report_generation(request_id: str, config: dict = None):
    """Run the report generation process in a background thread."""
    try:
        main(request_id=request_id, config=config)
    except Exception as e:
        # Log any errors that occur during report generation
        print(f"Error in report generation: {str(e)}")

@app.post("/api/generate-report")
async def generate_report(request: ReportGenerationRequest, background_tasks: BackgroundTasks):
    """Endpoint to start report generation process with custom configuration.
    
    Returns:
        dict: Contains the request_id that can be used to track the report generation progress.
    """
    # Generate a unique request ID
    request_id = f"{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8]}"
    
    # Start the report generation process in a background thread with custom config
    background_tasks.add_task(run_report_generation, request_id, request.config.dict())
    
    return {
        "status": "started",
        "request_id": request_id,
        "message": "Report generation process has been started. You can use the request_id to track progress."
    }

@app.get("/api/logs/{request_id}")
async def get_request_logs(request_id: str):
    """Get logs for a specific request ID.
    
    Args:
        request_id: The request ID to get logs for.
        
    Returns:
        List[Dict[str, str]]: List of log entries with timestamp, status, and message.
        
    Raises:
        HTTPException: If the log file doesn't exist.
    """
    log_file = os.path.join("system_log", f"request_{request_id}.csv")
    
    if not os.path.exists(log_file):
        raise HTTPException(
            status_code=404,
            detail=f"No logs found for request ID: {request_id}"
        )
    
    logs = []
    with open(log_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            logs.append({
                "timestamp": row["Timestamp"],
                "status": row["Status"],
                "message": row["Message"]
            })
    return logs

@app.get("/api/metrics/{request_id}")
async def get_request_metrics(request_id: str):
    """Get metrics for a specific request ID from logging.csv.
    
    Args:
        request_id: The request ID to get metrics for.
        
    Returns:
        List[Dict[str, str]]: List of metric entries with all token usage and cost information.
        
    Raises:
        HTTPException: If the logging.csv file doesn't exist or no metrics found for request_id.
    """
    if not os.path.exists("logging.csv"):
        raise HTTPException(
            status_code=404,
            detail="No metrics found (logging.csv does not exist)"
        )
    
    metrics = []
    with open("logging.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Request ID"] == request_id:
                metrics.append({
                    "timestamp": row["Timestamp"],
                    "section": row["Section"],
                    "model_version": row["Model Version"],
                    "input_tokens": row["Input Tokens"],
                    "output_tokens": row["Output Tokens"],
                    "total_tokens": row["Total Tokens"],
                    "cost_per_1m_input": row["Cost per 1M Input ($)"],
                    "cost_per_1m_output": row["Cost per 1M Output ($)"],
                    "input_cost": row["Input Cost ($)"],
                    "output_cost": row["Output Cost ($)"],
                    "total_cost": row["Total Cost ($)"]
                })
    
    if not metrics:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics found for request ID: {request_id}"
        )
        
    return metrics

@app.get("/api/statistics", response_model=StatisticsResponse)
async def get_statistics(
    start_date: str = Query(None, description="Start date for filtering (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date for filtering (YYYY-MM-DD)")
):
    """Get aggregated statistics from logging.csv for front-end display.
    
    Args:
        start_date: Optional start date for filtering (YYYY-MM-DD).
        end_date: Optional end date for filtering (YYYY-MM-DD).
        
    Returns:
        Dict: Aggregated statistics including cost overview, token usage, request volume, model usage, and high-impact requests.
        
    Raises:
        HTTPException: If logging.csv does not exist or no data found.
    """
    if not os.path.exists("logging.csv"):
        raise HTTPException(
            status_code=404,
            detail="No metrics found (logging.csv does not exist)"
        )
    
    # Load the CSV file
    df = pd.read_csv("logging.csv")
    
    # Convert Timestamp to datetime
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    
    # Apply date filtering if provided
    if start_date and end_date:
        try:
            df = df[
                (df["Timestamp"] >= start_date) & (df["Timestamp"] <= end_date)
            ]
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format or range: {str(e)}"
            )
    
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail="No data found for the specified date range"
        )
    
    # Compute statistics
    # 1. Cost Overview
    total_cost = df["Total Cost ($)"].sum()
    cost_by_model = df.groupby("Model Version")["Total Cost ($)"].sum().to_dict()
    # Convert datetime.date keys to strings
    cost_trend = df.groupby(df["Timestamp"].dt.date)["Total Cost ($)"].sum()
    cost_trend = {str(date): value for date, value in cost_trend.to_dict().items()}
    
    # 2. Token Usage
    total_tokens = df["Total Tokens"].sum()
    input_tokens = df["Input Tokens"].sum()
    output_tokens = df["Output Tokens"].sum()
    tokens_by_model = df.groupby("Model Version")["Total Tokens"].sum().to_dict()
    
    # 3. Request Volume
    total_requests = len(df)
    requests_by_model = df.groupby("Model Version").size().to_dict()
    # Convert datetime.date keys to strings
    requests_over_time = df.groupby(df["Timestamp"].dt.date).size()
    requests_over_time = {str(date): value for date, value in requests_over_time.to_dict().items()}
    
    # 4. Model Usage
    avg_tokens_per_request = df.groupby("Model Version")["Total Tokens"].mean().to_dict()
    avg_cost_per_request = df.groupby("Model Version")["Total Cost ($)"].mean().to_dict()
    
    # 5. High-Impact Requests
    top_cost_requests = (
        df[["Request ID", "Timestamp", "Model Version", "Total Tokens", "Total Cost ($)"]]
        .nlargest(5, "Total Cost ($)")
        .to_dict("records")
    )
    top_token_requests = (
        df[["Request ID", "Timestamp", "Model Version", "Total Tokens", "Total Cost ($)"]]
        .nlargest(5, "Total Tokens")
        .to_dict("records")
    )
    
    return {
        "cost_overview": {
            "total_cost": total_cost,
            "cost_by_model": cost_by_model,
            "cost_trend": cost_trend,
        },
        "token_usage": {
            "total_tokens": total_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tokens_by_model": tokens_by_model,
        },
        "request_volume": {
            "total_requests": total_requests,
            "requests_by_model": requests_by_model,
            "requests_over_time": requests_over_time,
        },
        "model_usage": {
            "requests_by_model": requests_by_model,
            "avg_tokens_per_request": avg_tokens_per_request,
            "avg_cost_per_request": avg_cost_per_request,
        },
        "high_impact_requests": {
            "top_cost_requests": top_cost_requests,
            "top_token_requests": top_token_requests,
        },
    }