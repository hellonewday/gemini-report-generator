import logging
import os
from typing import Dict, Any, Optional
from google.cloud import storage
from config import REPORT_CONFIG as DEFAULT_REPORT_CONFIG
from utils import log_to_request_file

logger = logging.getLogger(__name__)

def upload_to_gcs(pdf_file, request_id, config: Optional[Dict[str, Any]] = None):
    """Upload PDF file to Google Cloud Storage.
    
    Args:
        pdf_file: The path to the PDF file to upload.
        request_id: The request ID for logging.
        config: Optional configuration dictionary.
        
    Returns:
        str: The public URL of the uploaded file.
        
    Raises:
        Exception: If the upload fails.
    """
    try:
        logger.info("📤 Uploading PDF to Google Cloud Storage...")
        log_to_request_file(request_id, "uploading", "📤 Uploading PDF to Google Cloud Storage...")
        
        # Use provided config or fall back to default
        report_config = config or DEFAULT_REPORT_CONFIG
        
        storage_client = storage.Client(project="nth-droplet-458903-p4")
        bucket = storage_client.bucket('credit-card-reports')
        language_folder = report_config['language'].lower()
        blob_name = f"{language_folder}/{os.path.basename(pdf_file)}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(pdf_file, content_type='application/pdf')
        blob.make_public()
        public_url = blob.public_url
        
        msg = f"✅ PDF uploaded successfully to {language_folder} folder: {blob_name}"
        logger.info(msg)
        log_to_request_file(request_id, "uploading", msg)
        
        
        return public_url
    except Exception as e:
        msg = f"❌ Error in PDF upload: {str(e)}"
        logger.error(msg)
        log_to_request_file(request_id, "error", msg)
        raise