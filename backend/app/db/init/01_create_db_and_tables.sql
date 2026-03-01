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

  url text NOT NULL,
  title text,
  source text,
  description text,
  published_at timestamptz,
  inserted_at timestamptz DEFAULT now(),

  CONSTRAINT articles_url_unique UNIQUE (url),

  -- FinBERT sentiment fields (per url+stock row)
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

  gpt_expl_30d  text,
  gpt_expl_120d text,
  gpt_expl_360d text,

  gpt_model text,
  gpt_generated_at timestamptz,

  created_at timestamptz DEFAULT now(),

  CONSTRAINT uq_snapshots_ticker_date UNIQUE (ticker, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_date 
  ON sentiment_snapshots (ticker, snapshot_date);

CREATE INDEX IF NOT EXISTS idx_snapshot_ticker 
  ON sentiment_snapshots (ticker);

-- Article Ticker Sentiment table

CREATE TABLE IF NOT EXISTS article_ticker_sentiment (
  id SERIAL PRIMARY KEY,
  article_id UUID NOT NULL,
  article_url TEXT NOT NULL,
  ticker VARCHAR(20) NOT NULL,
  relevance_score NUMERIC,
  ticker_sentiment_score NUMERIC,
  ticker_sentiment_label VARCHAR(50),
  published_at TIMESTAMPTZ,
  
  CONSTRAINT fk_article
    FOREIGN KEY (article_id)
    REFERENCES articles(id)
    ON DELETE CASCADE,

  CONSTRAINT uq_article_ticker UNIQUE (article_id, ticker)
);

ALTER TABLE article_ticker_sentiment ADD COLUMN IF NOT EXISTS article_id UUID;

CREATE INDEX IF NOT EXISTS idx_article_ticker_sentiment_ticker
  ON article_ticker_sentiment (ticker);

CREATE INDEX IF NOT EXISTS idx_article_ticker_sentiment_article
  ON article_ticker_sentiment (article_id);

ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT;

ALTER TABLE sentiment_snapshots ADD COLUMN IF NOT EXISTS gpt_expl_30d text;
ALTER TABLE sentiment_snapshots ADD COLUMN IF NOT EXISTS gpt_expl_120d text;
ALTER TABLE sentiment_snapshots ADD COLUMN IF NOT EXISTS gpt_expl_360d text;
ALTER TABLE sentiment_snapshots ADD COLUMN IF NOT EXISTS gpt_model text;
ALTER TABLE sentiment_snapshots ADD COLUMN IF NOT EXISTS gpt_generated_at timestamptz;