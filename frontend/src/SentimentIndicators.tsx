import React from "react";
import type { SentimentLabel, StockIndicators } from "./utils/sentiment";

interface BadgeProps {
  label: SentimentLabel;
}

const sentimentClass = (label: SentimentLabel) => {
  switch (label) {
    case "bullish":
      return "indicator indicator-bullish";
    case "bearish":
      return "indicator indicator-bearish";
    case "neutral":
    default:
      return "indicator indicator-neutral";
  }
};

const SentimentBadge: React.FC<BadgeProps> = ({ label }) => (
  <span className={sentimentClass(label)}>{label}</span>
);

interface StockCardProps {
  data: StockIndicators;
}

export const StockSentimentCard: React.FC<StockCardProps> = ({ data }) => {
  const { ticker, indicators } = data;

  return (
    <div className="sentiment-card">
      <h3>{ticker} Sentiment</h3>
      <div className="indicator-row">
        <span>30 days:</span>
        <SentimentBadge label={indicators.d30} />
      </div>
      <div className="indicator-row">
        <span>120 days:</span>
        <SentimentBadge label={indicators.d120} />
      </div>
      <div className="indicator-row">
        <span>360 days:</span>
        <SentimentBadge label={indicators.d360} />
      </div>
    </div>
  );
};