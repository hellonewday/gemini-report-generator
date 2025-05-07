from typing import NamedTuple, Optional
from google.genai.types import GroundingMetadata

class ReportSection(NamedTuple):
    """Represents a section in the report."""
    title: str
    content: str
    grounding_metadata: Optional[GroundingMetadata] = None 