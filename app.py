import csv
import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI()

# CORS setup for local frontend apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/logs")
async def get_logs():
    """Retrieve LLM usage logs from logging.csv in JSON format."""
    try:
        logs = []
        if os.path.exists("logging.csv"):
            with open("logging.csv", 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    logs.append(row)
        return JSONResponse(content=logs)
    except Exception as e:
        logger.error(f"Error reading logs: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
