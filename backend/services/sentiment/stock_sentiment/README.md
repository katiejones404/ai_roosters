## Stock Processing Pipeline

This will show you how to generate the returns from the stock data 

## How to run: 

in the terminal run: 

docker exec -it stock_backend bash

python services/sentiment/stock_sentiment/stock_processing.py


## How to fix if no stock data 

docker exec -it stock_backend bash

python /app/services/prices_ingest.py