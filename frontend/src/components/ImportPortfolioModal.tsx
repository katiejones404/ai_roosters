import React, { useState, useEffect, useRef } from 'react';
import axios from "axios";
import { getToken } from '../utils/auth';
import { TICKER_NAMES } from '../utils/stockNames';
import './ImportPortfolio.css';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');

interface StockOption {
  ticker: string;
  close: number | null;
}

interface ImportEntry {
  id: string;
  ticker: string;
  quantity: string;
  avg_price: string;
  status: "idle" | "saving" | "saved" | "error";
  error?: string;
}

interface ImportPortfolioMoalProps {
    onClose: () => void;
    onSuccess: () => void;
}

const genId = () => Math.random().toString(36).substr(2, 9);

const emptyEntry = (): ImportEntry => ({
    id: genId(),
    ticker: "",
    quantity: "",
    avg_price: "",
    status: "idle",
});

interface TickerSearchProps {
  value: string;
  onChange: (ticker: string) => void;
  allStocks: StockOption[];
  disabled: boolean;
}

// Ticker search dropdown component

const TickerSearch: React.FC<TickerSearchProps> = ({ value, onChange, allStocks, disabled }) => {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
  }, []);

  const filtered = query.trim()
    ? allStocks
      .filter(
        (s) =>
          s.ticker.toUpperCase().includes(query.toUpperCase()) ||
          (TICKER_NAMES[s.ticker] || "").toLowerCase().includes(query.toLowerCase())
    )
    .slice(0, 8)
  : allStocks.slice(0, 8);

  const handleSelect = (ticker: string) => {
    setQuery(ticker);
    onChange(ticker);
    setOpen(false);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.toUpperCase();
    setQuery(val);
    onChange(val);
    setOpen(true);
  };

  return (
    <div className="imp-ticker-wrap" ref={wrapRef}>
      <input
        className="imp-input imp-input-ticker"
        placeholder="Search ticker..."
        value={query}
        onChange={handleChange}
        onFocus={() => setOpen(true)}
        disabled={disabled}
        maxLength={10}
        autoComplete="off"
      />
      {open && filtered.length > 0 && (
        <div className="imp-ticker-dropdown">
          {filtered.map((s) => (
            <div
              key={s.ticker}
              className="imp-ticker-option"
              onMouseDown={() => handleSelect(s.ticker)}
            >
              <span className="imp-ticker-opt-symbol">{s.ticker}</span>
              <span className="imp-ticker-opt-name">{TICKER_NAMES[s.ticker] || ""}</span>
              {s.close != null && (
                <span className="imp-ticker-opt-price">${s.close.toFixed(2)}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Main modal component

const ImportPortfolioModal: React.FC<ImportPortfolioMoalProps> = ({ onClose, onSuccess }) => {
    const [entries, setEntries] = useState<ImportEntry[]>([emptyEntry()]);
    const [submitting, setSubmitting] = useState(false);
    const [globalError, setGlobalError] = useState<string | null>(null);
    const [allStocks, setAllStocks] = useState<StockOption[]>([]);

    useEffect(() => {
      axios.get<StockOption[]>(`${API_BASE}/api/stocks/latest`)
      .then((res) => setAllStocks(res.data.filter((s) => s.close !== null)))
      .catch(() => setAllStocks([]));
    }, []);

    const updateEntry = (id: string, field: keyof ImportEntry, value: string) => {
        setEntries((prev) => 
            prev.map((e) => 
            e.id === id ? { ...e, [field]: field === "ticker" ? value.toUpperCase() : value, status: "idle", error: undefined } : e
            )
        );
    };

    const addRow = () => setEntries((prev) => [...prev, emptyEntry()]);

    const removeRow = (id: string) => {
        if (entries.length === 1) return;
        setEntries((prev) => prev.filter((e) => e.id !== id))
    };

    const validateEntries = (e: ImportEntry): string | null => {
        if (!e.ticker.trim()) return "Ticker is required";
        const qty = parseFloat(e.quantity);
        if (isNaN(qty) || qty <= 0) return "Quantity must be a positive number";
        const price = parseFloat(e.avg_price);
        if (isNaN(price) || price < 0) return "Average price must be a non-negative number";
        return null;
    };

    const handleImport = async () => {
        setGlobalError(null);

        let hasError = false;
        const validated = entries.map((e) => {
            const err = validateEntries(e);
            if (err) { hasError = true; return { ...e, status: "error" as const, error: err}; }
            return e;
        });
        if (hasError) { setEntries(validated); return; }

        setSubmitting(true);
        const token = getToken();
        if (!token) { setGlobalError("You must be logged in."); setSubmitting(false); return; }

        const results = await Promise.all(
            entries.map(async (e) => {
                try {
                    await axios.post(
                        `${API_BASE}/api/portfolio`,
                        { ticker: e.ticker.trim(), quantity: parseFloat(e.quantity), avg_price: parseFloat(e.avg_price) },
                        { headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } }
                    );
                    return { ...e, status: "saved" as const };
                } catch (err: any) {
                    const detail = err.response?.data?.detail;
                    const msg = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d: any) => d.msg).join(", "): "Failed to import";
                    return { ...e, status: "error" as const, error: msg };
                }
            })
        );

        setEntries(results);
        setSubmitting(false);

        const allSaved = results.every((r) => r.status === "saved");
        if (allSaved) setTimeout(onSuccess, 400);
    };

    const savedCount = entries.filter((e) => e.status === "saved").length;
    const allDone = entries.length > 0 && entries.every((e) => e.status === "saved");

    return (
    <div className="imp-backdrop" onClick={(ev) => ev.target === ev.currentTarget && onClose()}>
      <div className="imp-modal">
        {/* Header */}
        <div className="imp-header">
            <div>
              <h2 className="imp-title">Import Your Portfolio</h2>
              <p className="imp-subtitle">Add stocks you already own at the price you paid</p>
            </div>
          <button className="imp-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
 
        {/* Column headers */}
        <div className="imp-col-headers">
          <span>Ticker</span>
          <span>Shares Owned</span>
          <span>Purchase Price / Share</span>
          <span>Total Cost</span>
          <span></span>
        </div>
 
        {/* Rows */}
        <div className="imp-rows">
          {entries.map((entry) => {
            const qty = parseFloat(entry.quantity);
            const price = parseFloat(entry.avg_price);
            const total = !isNaN(qty) && !isNaN(price) && qty > 0 && price > 0 ? qty * price : null;
            const isSaved = entry.status === "saved";
 
            return (
              <div key={entry.id} className={`imp-row ${entry.status === "error" ? "imp-row-error" : ""} ${isSaved ? "imp-row-saved" : ""}`}>
                {/* Ticker search */}
                <div className="imp-field imp-field-ticker">
                  <TickerSearch
                    value={entry.ticker}
                    onChange={(val) => updateEntry(entry.id, "ticker", val)}
                    allStocks={allStocks}
                    disabled={isSaved || submitting}
                  />
                </div>
                { /* Quantity */}
                <div className="imp-field">
                  <input
                    className="imp-input"
                    type="number"
                    placeholder="e.g. 10"
                    min="0.0001"
                    step="any"
                    value={entry.quantity}
                    onChange={(e) => updateEntry(entry.id, "quantity", e.target.value)}
                    disabled={isSaved || submitting}
                  />
                </div>
                {/* Purchase price */}
                <div className="imp-field">
                  <div className="imp-input-prefix-wrap">
                    <span className="imp-prefix">$</span>
                    <input
                      className="imp-input imp-input-prefixed"
                      type="number"
                      placeholder="0.00"
                      min="0.0001"
                      step="any"
                      value={entry.avg_price}
                      onChange={(e) => updateEntry(entry.id, "avg_price", e.target.value)}
                      disabled={isSaved || submitting}
                    />
                  </div>
                </div>
                {/* Total cost */}
                <div className="imp-field imp-field-total">
                  {total !== null ? (
                    <span className="imp-total-val">
                      ${total.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  ) : (
                    <span className="imp-total-empty">-</span>
                  )}
                </div>
                {/* Remove button */}
                <div className="imp-field imp-field-action">
                  {!isSaved ? (
                    <span className="imp-saved-badge">✓</span>
                  ) : (
                    <button
                      className="imp-remove-btn"
                      onClick={() => removeRow(entry.id)}
                      disabled={entries.length === 1 || submitting}
                      aria-label="Remove row"
                    >
                      ✕
                    </button>
                  )}
                </div>

                {entry.status === "error" && entry.error && (
                  <div className="imp-row-err-msg">{entry.error}</div>
                )}
              </div>
            );
          })}
        </div>

        {!allDone && (
          <button className="imp-add-row-btn" onClick={addRow} disabled={submitting}>
            + Add Another Stock
          </button>
        )}

        {globalError && <p className="imp-global-error">{globalError}</p>}

        {savedCount > 0 && !allDone && (
          <p className="imp-progress">
            {savedCount} of {entries.length} saved — fix errors above to continue.
          </p>
        )}

        {/* Footer */}
        <div className="imp-footer">
          <button className="imp-cancel-btn" onClick={onClose} disabled={submitting}>
            {allDone ? "Close" : "Cancel"}
          </button>
          {!allDone && (
            <button
              className="imp-confirm-btn"
              onClick={handleImport}
              disabled={submitting || entries.length === 0}
            >
              {submitting ? (
                <><span className="imp-spinner" />Importing...</>
              ) : (
                `Import ${entries.length} Position${entries.length !== 1 ? "s" : ""}`
              )}
            </button>
          )}
        </div>
      
      </div>
    </div>
  );
};

export default ImportPortfolioModal;