import logging
import os
from google.cloud import storage
from config import REPORT_CONFIG

logger = logging.getLogger(__name__)

def upload_to_gcs(pdf_file, current_request_id):
    """Upload PDF file to Google Cloud Storage."""
    logger.info("📤 Uploading PDF to Google Cloud Storage...")
    try:
        storage_client = storage.Client(project="nth-droplet-458903-p4")
        bucket = storage_client.bucket('credit-card-reports')
        language_folder = REPORT_CONFIG['language'].lower()
        blob_name = f"{language_folder}/{os.path.basename(pdf_file)}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(pdf_file, content_type='application/pdf')
        blob.make_public()
        public_url = blob.public_url
        logger.info(f"✅ PDF uploaded successfully to {language_folder} folder: {blob_name}")
        logger.info(f"🔗 Public URL: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"❌ Error in PDF upload: {str(e)}")
        raise