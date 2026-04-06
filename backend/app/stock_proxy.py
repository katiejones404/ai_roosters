"""
Notes - Proxy endpoint for fetching historical stock price data from Yahoo Finance.
Forwards ticker, date range, and interval to Yahoo’s chart API and returns the raw JSON.
"""

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

@router.get("/api/stock-history")
async def stock_history(
    ticker: str = Query(...),
    period1: int = Query(...),
    period2: int = Query(...),
    interval: str = Query(default="1mo"),
):
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}"
        f"?period1={period1}&period2={period2}&interval={interval}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="Yahoo Finance error")
        except Exception:
            raise HTTPException(status_code=502, detail="Could not reach market data")
