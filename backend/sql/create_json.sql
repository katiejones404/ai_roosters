-- sql/create_articles_tables.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS articles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text,
  author text,
  published_at timestamptz,
  source text,
  url text UNIQUE,
  image text,
  category text,
  language text,
  country text,
  raw jsonb,
  inserted_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stocks (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(20) NOT NULL,
  date DATE NOT NULL,
  adjusted_close NUMERIC NULL,
  open NUMERIC,
  high NUMERIC,
  low NUMERIC,
  close NUMERIC,
  volume BIGINT,
  CONSTRAINT uq_ticker_date UNIQUE (ticket, date)
)


CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles (published_at);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles (source);
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles (url);
CREATE INDEX IF NOT EXISTS idx_articles_raw_gin ON articles USING gin (raw);
