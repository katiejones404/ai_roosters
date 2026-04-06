/*
 * SentimentIndicators.tsx
 * Reusable card that shows sentiment labels and the AI news summary for a stock.
 */
import React from "react";
import type { StockIndicators, SentimentLabel, StockNewsExplanations } from "./utils/sentiment";

type StockCardProps = {
  // Stock data passed into the card
  data: StockIndicators;
};

// Text color for each sentiment label
const labelColor = (label: SentimentLabel): string => {
  if (label === "bullish") return "#22c55e";
  if (label === "bearish") return "#ef4444";
  return "#cbd5e1";
};

// Background color for each sentiment label
const labelBg = (label: SentimentLabel): string => {
  if (label === "bullish") return "rgba(22, 163, 74, 0.18)";
  if (label === "bearish") return "rgba(220, 38, 38, 0.18)";
  return "rgba(100, 116, 139, 0.24)";
};

// Makes the range key easier to read in the UI
const prettyRange = (k: "d30" | "d120" | "d360") => {
  if (k === "d30") return "30D";
  if (k === "d120") return "120D";
  return "360D";
};

// Makes the label text look cleaner
const prettyLabel = (l: SentimentLabel) => {
  if (l === "bullish") return "Bullish";
  if (l === "bearish") return "Bearish";
  return "Neutral";
};

// Formats backend dates into a simple readable format
const formatDate = (value?: string | null): string | null => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

// Picks the best news summary to show first
const getPreferredNews = (news?: StockNewsExplanations | null) => {
  if (!news) return null;

  // Prefer 7-day news when it has articles
  if (news.d7 && news.d7.article_count > 0) {
    return { label: "7D News Summary", windowDays: 7, window: news.d7, isFallback: false };
  }

  // Fall back to 30-day news when needed
  if (news.d30 && news.d30.article_count > 0) {
    return { label: "30D News Summary", windowDays: 30, window: news.d30, isFallback: true };
  }

  // Still allow empty summaries to render if they exist
  if (news.d7) {
    return { label: "7D News Summary", windowDays: 7, window: news.d7, isFallback: false };
  }
  if (news.d30) {
    return { label: "30D News Summary", windowDays: 30, window: news.d30, isFallback: true };
  }

  return null;
};

export const StockSentimentCard: React.FC<StockCardProps> = ({ data }) => {
  // The sentiment windows shown in the top cards
  const ranges: Array<"d30" | "d120" | "d360"> = ["d30", "d120", "d360"];

  // Best available news summary for this stock
  const preferredNews = getPreferredNews(data.news_explanations);

  // Human-readable latest article date
  const latestArticleDate = formatDate(preferredNews?.window.latest_article_at);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {/* Top row: sentiment boxes for each time range */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14 }}>
        {ranges.map((k) => {
          const label = data.indicators[k];

          return (
            <div
              key={k}
              style={{
                border: "1px solid rgba(148, 163, 184, 0.22)",
                borderRadius: 14,
                padding: 16,
                background: "rgba(15, 23, 42, 0.74)",
              }}
            >
              <div style={{ fontSize: 12, color: "#94a3b8", fontWeight: 700, letterSpacing: "0.08em" }}>
                {prettyRange(k)} SENTIMENT
              </div>

              <div style={{ marginTop: 12 }}>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    padding: "6px 12px",
                    borderRadius: 999,
                    color: labelColor(label),
                    background: labelBg(label),
                    border: "1px solid rgba(148, 163, 184, 0.22)",
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                  }}
                >
                  {prettyLabel(label)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Bottom card: AI-generated news explanation */}
      <div
        style={{
          border: "1px solid rgba(148, 163, 184, 0.22)",
          borderRadius: 14,
          padding: 18,
          background: "rgba(15, 23, 42, 0.74)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 12, color: "#94a3b8", fontWeight: 700, letterSpacing: "0.08em" }}>
              AI NEWS EXPLANATION
            </div>
            <div style={{ marginTop: 6, fontSize: 18, fontWeight: 700, color: "#e2e8f0" }}>
              {preferredNews?.label ?? "News Summary"}
            </div>
          </div>

          {/* Small tags showing which summary was used and article count */}
          {preferredNews && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "5px 10px",
                  borderRadius: 999,
                  color: preferredNews.isFallback ? "#c4b5fd" : "#7dd3fc",
                  background: preferredNews.isFallback ? "rgba(76, 29, 149, 0.34)" : "rgba(12, 74, 110, 0.34)",
                  border: "1px solid rgba(148, 163, 184, 0.22)",
                }}
              >
                {preferredNews.isFallback ? "30D fallback" : "7D primary"}
              </span>

              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "5px 10px",
                  borderRadius: 999,
                  color: "#cbd5e1",
                  background: "rgba(51, 65, 85, 0.5)",
                  border: "1px solid rgba(148, 163, 184, 0.22)",
                }}
              >
                {preferredNews.window.article_count} article{preferredNews.window.article_count === 1 ? "" : "s"}
              </span>
            </div>
          )}
        </div>

        {/* Main summary text */}
        <div style={{ marginTop: 12 }}>
          {preferredNews?.window.summary_text ? (
            <p style={{ margin: 0, color: "#cbd5e1", fontSize: 14, lineHeight: 1.6 }}>
              {preferredNews.window.summary_text}
            </p>
          ) : (
            <p style={{ margin: 0, color: "#94a3b8", fontSize: 14 }}>
              No AI news explanation available.
            </p>
          )}
        </div>

        {/* Extra metadata shown at the bottom when available */}
        {(latestArticleDate || data.news_explanations?.gpt_model || data.news_explanations?.gpt_generated_at) && (
          <div style={{ marginTop: 14, fontSize: 12, color: "#94a3b8", display: "flex", gap: 10, flexWrap: "wrap" }}>
            {latestArticleDate ? <span>Latest article: {latestArticleDate}</span> : null}
            {data.news_explanations?.gpt_model ? <span>Model: {data.news_explanations.gpt_model}</span> : null}
            {data.news_explanations?.gpt_generated_at ? (
              <span>Generated: {formatDate(data.news_explanations.gpt_generated_at) ?? data.news_explanations.gpt_generated_at}</span>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};