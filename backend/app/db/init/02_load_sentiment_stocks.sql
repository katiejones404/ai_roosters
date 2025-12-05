-- Load sentiment_snapshots.csv directly into the sentiment_snapshots table.
-- Expects CSV  at /data/sentiment_snapshots.csv

-- Treat 'NaN' as NULL when importing
COPY sentiment_snapshots(
    id,
    ticker,
    snapshot_date,
    close_price,
    return_1d,
    return_30d,
    return_120d,
    return_360d,
    sentiment_mean,
    sentiment_max,
    sentiment_min,
    num_articles,
    num_pos_articles,
    num_neg_articles,
    pos_share,
    neg_share,
    prob_pos_mean,
    prob_neg_mean,
    prob_neu_mean,
    prob_pos_max,
    prob_neg_max,
    created_at
)
FROM '/data/sentiment_snapshots.csv'
WITH (
    FORMAT csv,
    HEADER true,
    DELIMITER ',',
    NULL 'NaN'
);
