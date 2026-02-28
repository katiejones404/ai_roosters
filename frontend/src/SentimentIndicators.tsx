import React from "react";
import type { StockIndicators, SentimentLabel } from "./utils/sentiment";

type StockCardProps = {
  data: StockIndicators;
};

const labelColor = (label: SentimentLabel): string => {
  if (label === "bullish") return "#16a34a";
  if (label === "bearish") return "#dc2626";
  return "#64748b";
};

const labelBg = (label: SentimentLabel): string => {
  if (label === "bullish") return "#dcfce7";
  if (label === "bearish") return "#fee2e2";
  return "#f1f5f9";
};

const prettyRange = (k: "d30" | "d120" | "d360") => {
  if (k === "d30") return "30D";
  if (k === "d120") return "120D";
  return "360D";
};

const prettyLabel = (l: SentimentLabel) => {
  if (l === "bullish") return "Bullish";
  if (l === "bearish") return "Bearish";
  return "Neutral";
};

export const StockSentimentCard: React.FC<StockCardProps> = ({ data }) => {
  const ranges: Array<"d30" | "d120" | "d360"> = ["d30", "d120", "d360"];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
      {ranges.map((k) => {
        const label = data.indicators[k];
        const expl = data.explanations?.[k] ?? null;

        return (
          <div
            key={k}
            style={{
              border: "1px solid #e2e8f0",
              borderRadius: 14,
              padding: 16,
              background: "#fff",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
              <div style={{ fontSize: 12, color: "#94a3b8", fontWeight: 700, letterSpacing: "0.08em" }}>
                {prettyRange(k)} SENTIMENT
              </div>

              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 10px",
                  borderRadius: 999,
                  color: labelColor(label),
                  background: labelBg(label),
                  border: "1px solid #e2e8f0",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                {prettyLabel(label)}
              </span>
            </div>

            <div style={{ marginTop: 10 }}>
              {expl ? (
                <p style={{ margin: 0, color: "#334155", fontSize: 13, lineHeight: 1.45 }}>
                  {expl}
                </p>
              ) : (
                <p style={{ margin: 0, color: "#94a3b8", fontSize: 13 }}>
                  No GPT explanation available.
                </p>
              )}
            </div>

            {(data.gpt_model || data.gpt_generated_at) && (
              <div style={{ marginTop: 12, fontSize: 11, color: "#94a3b8" }}>
                {data.gpt_model ? <span style={{ fontWeight: 600 }}>{data.gpt_model}</span> : null}
                {data.gpt_model && data.gpt_generated_at ? " • " : null}
                {data.gpt_generated_at ? <span>{data.gpt_generated_at}</span> : null}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};