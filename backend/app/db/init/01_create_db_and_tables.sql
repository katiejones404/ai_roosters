CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- User Table
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username text UNIQUE NOT NULL,
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  created_at timestamptz DEFAULT now(),
  notify_email_enabled boolean NOT NULL DEFAULT true,
  notify_market_alerts_enabled boolean NOT NULL DEFAULT true,
  notify_portfolio_updates_enabled boolean NOT NULL DEFAULT true,
  notify_weekly_report_enabled boolean NOT NULL DEFAULT false,
  notify_push_enabled boolean NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- News Articles
CREATE TABLE IF NOT EXISTS stock_news_articles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker text NOT NULL,
  url text NOT NULL,
  title text,
  source text,
  description text,
  snippet text,
  image_url text,
  language text,
  published_at timestamptz,
  inserted_at timestamptz DEFAULT now(),
  relevance_score numeric,
  UNIQUE (ticker, url)
);

CREATE INDEX IF NOT EXISTS idx_stock_news_articles_ticker_published
  ON stock_news_articles (ticker, published_at DESC);

CREATE TABLE IF NOT EXISTS stock_news_summaries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker text NOT NULL,
  window_days int NOT NULL,
  summary_text text NOT NULL,
  article_count int NOT NULL DEFAULT 0,
  latest_article_at timestamptz,
  generated_at timestamptz NOT NULL DEFAULT now(),
  model text,
  UNIQUE (ticker, window_days)
);

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

  ticker text NOT NULL,
  snapshot_date date NOT NULL,

  close_price numeric,
  return_1d numeric,
  return_30d numeric,
  return_120d numeric,
  return_360d numeric,

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
ALTER TABLE users ADD COLUMN IF NOT EXISTS streak_current INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS streak_best INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS streak_last_visit DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS streak_visit_days TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS streak_total_visits INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_email_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_market_alerts_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_portfolio_updates_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_weekly_report_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_push_enabled BOOLEAN NOT NULL DEFAULT FALSE;

-- Net Worth: manual assets
CREATE TABLE IF NOT EXISTS networth_assets (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL,
  name        text NOT NULL,
  category    text NOT NULL,
  balance     numeric NOT NULL DEFAULT 0,
  updated_at  timestamptz DEFAULT now(),
  created_at  timestamptz DEFAULT now(),
  CONSTRAINT fk_nw_assets_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_networth_assets_user ON networth_assets (user_id);

-- Net Worth: manual liabilities
CREATE TABLE IF NOT EXISTS networth_liabilities (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL,
  name        text NOT NULL,
  category    text NOT NULL,
  balance     numeric NOT NULL DEFAULT 0,
  updated_at  timestamptz DEFAULT now(),
  created_at  timestamptz DEFAULT now(),
  CONSTRAINT fk_nw_liabilities_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_networth_liabilities_user ON networth_liabilities (user_id);

-- Net Worth: daily snapshots for history chart
CREATE TABLE IF NOT EXISTS networth_snapshots (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid NOT NULL,
  snapshot_date     date NOT NULL,
  portfolio_value   numeric NOT NULL DEFAULT 0,
  total_assets      numeric NOT NULL DEFAULT 0,
  total_liabilities numeric NOT NULL DEFAULT 0,
  net_worth         numeric NOT NULL DEFAULT 0,
  created_at        timestamptz DEFAULT now(),
  CONSTRAINT fk_nw_snapshots_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT uq_networth_snapshot UNIQUE (user_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_networth_snapshots_user_date
  ON networth_snapshots (user_id, snapshot_date DESC);


-- Price Alerts
CREATE TABLE IF NOT EXISTS price_alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  ticker text NOT NULL,
  target_price numeric NOT NULL,
  direction text NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  email_notify boolean NOT NULL DEFAULT true,
  triggered_at timestamptz,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT fk_price_alerts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_price_alerts_user ON price_alerts (user_id);
CREATE INDEX IF NOT EXISTS idx_price_alerts_active ON price_alerts (is_active) WHERE is_active = true;
