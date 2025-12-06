CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- User Table
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username text UNIQUE NOT NULL,
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- Articles

CREATE TABLE IF NOT EXISTS articles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  published_at timestamptz,
  title text,
  description text,
  url text UNIQUE,
  inserted_at timestamptz DEFAULT now(),

  -- FinBERT sentiment fields (per article)
  sentiment text,
  sentiment_score numeric,
  prob_pos numeric,
  prob_neg numeric,
  prob_neu numeric
);

CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles (published_at);
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles (url);
CREATE INDEX IF NOT EXISTS idx_articles_sentiment ON articles (sentiment);

-- User Portfolio
CREATE TABLE IF NOT EXISTS portfolio (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  user_id uuid NOT NULL,
  ticker text NOT NULL,
  quantity numeric NOT NULL,
  avg_price numeric NOT NULL,
  added_at timestamptz DEFAULT now(),

  CONSTRAINT fk_items_user
    FOREIGN KEY (user_id)
    REFERENCES users(id)
    ON DELETE CASCADE
);

-- Stocks

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

  return_1d   NUMERIC,
  return_30d  NUMERIC,
  return_120d NUMERIC,
  return_360d NUMERIC, 

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  CONSTRAINT uq_ticker_date UNIQUE (ticker, date)
);

-- Kevin: Sentiment database 

CREATE TABLE IF NOT EXISTS sentiment_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Which stock this snapshot for 
  ticker text NOT NULL, 
  -- The date of the snapshot 
  snapshot_date date NOT NULL,
  
  close_price numeric, 
  return_1d numeric, 
  return_30d numeric, 
  return_120d numeric, 
  return_360d numeric, 

  -- Sentiment stats 

  sentiment_mean numeric, 
  sentiment_max numeric, 
  sentiment_min numeric, 

  num_articles integer, 
  num_pos_articles integer, 
  num_neg_articles integer, 

  pos_share numeric, 
  neg_share numeric, 

  prob_pos_mean numeric, 
  prob_neg_mean numeric, 
  prob_neu_mean numeric, 

  prob_pos_max numeric, 
  prob_neg_max numeric, 

  created_at timestamptz DEFAULT now(),

  CONSTRAINT uq_snapshots_ticker_date UNIQUE (ticker, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_date 
  ON sentiment_snapshots (ticker, snapshot_date);

CREATE INDEX IF NOT EXISTS idx_snapshot_ticker 
  ON sentiment_snapshots (ticker);