from pydantic import BaseModel, Field
from typing import Optional, Literal

class SentimentRequest(BaseModel):
    """Incoming text to analyze for sentiment."""
    text: str = Field(..., description="Financial news, tweet, or comment text")

class SentimentResponse(BaseModel):
    """Output after model inference."""
    sentiment: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    ticker: Optional[str] = Field(None, description="Detected stock ticker symbol (if any)")
