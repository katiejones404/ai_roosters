// frontend/src/SentimentIndicators.tsx
import React from "react";
import type { SentimentLabel, StockIndicators } from "./utils/sentiment";

interface StockCardProps {
  data: StockIndicators;
  onDelete?: (ticker: string) => void | Promise<void>;
}

/**
 * Simple 3-slice “pie chart” using SVG.
 * Only the slice for the current sentiment label is colored;
 * the other two are light gray.
 */
const SentimentPie: React.FC<{ label: SentimentLabel }> = ({ label }) => {
  const size = 64;
  const radius = 26;
  const center = size / 2;
  const circumference = 2 * Math.PI * radius;
  const segment = circumference / 3;

  const segments: { key: SentimentLabel; offset: number }[] = [
    { key: "bullish", offset: 0 },
    { key: "neutral", offset: segment },
    { key: "bearish", offset: 2 * segment },
  ];

  const colorMap: Record<SentimentLabel, string> = {
    bullish: "#16a34a", // green
    neutral: "#6b7280", // gray
    bearish: "#dc2626", // red
  };

  return (
    <svg
      className="sentiment-pie"
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
    >
      {segments.map((seg) => {
        const active = seg.key === label;
        return (
          <circle
            key={seg.key}
            cx={center}
            cy={center}
            r={radius}
            fill="transparent"
            stroke={active ? colorMap[seg.key] : "#e5e7eb"}
            strokeWidth={10}
            strokeDasharray={`${segment} ${circumference - segment}`}
            strokeDashoffset={-seg.offset}
            strokeLinecap="round"
          />
        );
      })}
    </svg>
  );
};

export const StockSentimentCard: React.FC<StockCardProps> = ({
  data,
  onDelete,
}) => {
  const { ticker, snapshot_date, close_price, indicators } = data;
  const dateStr = new Date(snapshot_date).toISOString().slice(0, 10);

  const prettyLabel = (l: SentimentLabel) =>
    l.charAt(0).toUpperCase() + l.slice(1); // "bullish" -> "Bullish"

  return (
    <div className="sentiment-card">
      <div className="sentiment-card-header">
        <div>
          <h3>{ticker}</h3>
          <div className="sentiment-meta">
            <span>{dateStr}</span>
            {close_price != null && (
              <span className="sentiment-price">${close_price.toFixed(2)}</span>
            )}
          </div>
        </div>

        {onDelete && (
          <button
            className="sentiment-delete-btn"
            onClick={() => onDelete(ticker)}
            aria-label={`Remove ${ticker}`}
          >
            ×
          </button>
        )}
      </div>

      <div className="sentiment-pies">
        <div className="sentiment-pie-group">
          <SentimentPie label={indicators.d30} />
          <span className="sentiment-pie-label">30 days</span>
          <span className="sentiment-pie-value">
            {prettyLabel(indicators.d30)}
          </span>
        </div>
        <div className="sentiment-pie-group">
          <SentimentPie label={indicators.d120} />
          <span className="sentiment-pie-label">120 days</span>
          <span className="sentiment-pie-value">
            {prettyLabel(indicators.d120)}
          </span>
        </div>
        <div className="sentiment-pie-group">
          <SentimentPie label={indicators.d360} />
          <span className="sentiment-pie-label">360 days</span>
          <span className="sentiment-pie-value">
            {prettyLabel(indicators.d360)}
          </span>
        </div>
      </div>
    </div>
  );
};
