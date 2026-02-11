#How API is being run to update csv file in data/article_api_data

# run_ingest.py
from alphavantage_ingest import ingest_for_tickers

# Get articles 
#Change ticker if needed
tickers = ["AMZN"]
ingest_for_tickers(
    tickers=tickers,
    time_from="20250101T0000",  # January 1, 2025 at midnight change time/date if needed
    time_to="20250220T2359",     #February 20th, 2025 at 11:59 PM change time/date if needed
    limit=1000  # Request more articles (API may cap this)
)