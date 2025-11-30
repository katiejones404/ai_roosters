## Article processing pipeline 

This will show you how to use and create the data in the articles database if it's missing

## How to run: 

in the terminal run: 

docker exec -it stock_backend bash

NEWS_CSV_PATH=data/reliance_news_sentiment.csv python services/sentiment/article_sentiment/article_processing.py