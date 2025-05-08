# Credit Card Report Generator

A WebSocket-based application for generating credit card market analysis reports, with a FastAPI backend and React.js frontend.

## Prerequisites

- Python 3.8+
- Node.js 16+
- wkhtmltopdf (install from https://wkhtmltopdf.org/downloads.html)
- Google Cloud credentials for GCS access
- Required Python packages: `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`, `google-cloud-storage`, `pdfkit`, `markdown`, and others (see `requirements.txt`)

## Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Backend Setup**:
   - Create a virtual environment and install dependencies:
     ```bash
     python -m venv venv
     source venv/bin/activate  # On Windows: venv\Scripts\activate
     pip install -r requirements.txt
     ```
   - Set environment variables in a `.env` file:
     ```
     GOOGLE_CLOUD_PROJECT=nth-droplet-458903-p4
     WKHTMLTOPDF_PATH=C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe  # Adjust for your system
     ```
   - Run the FastAPI server:
     ```bash
     uvicorn app:app --host 0.0.0.0 --port 8000
     ```

3. **Frontend Setup**:
   - Navigate to the `frontend` directory:
     ```bash
     cd frontend
     ```
   - Install dependencies:
     ```bash
     npm install
     ```
   - Run the React development server:
     ```bash
     npm start
     ```
   - The frontend will be available at `http://localhost:3000`.

## Usage

1. Open the frontend in a browser (`http://localhost:3000`).
2. Click "Generate Report" to start the report generation process.
3. Watch logs stream in real-time in the log viewer.
4. Once complete, a link to the generated report will appear.
5. If an error occurs, an error message will be displayed.

## API Endpoints

- **WebSocket**: `ws://localhost:8000/ws/report`
  - Send a JSON payload with the `REPORT_CONFIG` to generate a report.
  - Receives log messages and the final public URL or error message.
- **GET**: `http://localhost:8000/api/logs`
  - Returns the contents of `logging.csv` in JSON format.

## Development Notes

- Ensure `wkhtmltopdf` is installed and accessible (set `WKHTMLTOPDF_PATH` if needed).
- The frontend uses Tailwind CSS for styling, loaded via CDN in the demo.
- For production, add authentication, rate limiting, and a task queue (e.g., Celery) for scalability.

## Troubleshooting

- **WebSocket errors**: Check the FastAPI server logs and ensure the backend is running.
- **PDF generation failures**: Verify `wkhtmltopdf` is installed and the path is correct.
- **CORS issues**: Ensure the frontend origin (`http://localhost:3000`) is allowed in the CORS middleware.