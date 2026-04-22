import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { getToken } from "../utils/auth";
import { TICKER_NAMES } from "../utils/stockNames";
import "./ImportPortfolio.css";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

interface StockOption {
  ticker: string;
  close: number | null;
}

interface ImportEntry {
  id: string;
  ticker: string;
  quantity: string;
  purchase_date: string;
  avg_price: string;
  price_found: number | null;
  price_loading: boolean;
  needs_manual_price: boolean;
  status: "idle" | "saving" | "saved" | "error";
  error?: string;
  minDate: string | null;
  minDateLoading: boolean;
}

interface ImportPortfolioMoalProps {
  onClose: () => void;
  onSuccess: () => void;
}

const genId = () => Math.random().toString(36).slice(2, 11);

const emptyEntry = (): ImportEntry => ({
  id: genId(),
  ticker: "",
  quantity: "",
  purchase_date: "",
  avg_price: "",
  price_found: null,
  price_loading: false,
  needs_manual_price: false,
  status: "idle",
  minDate: null,
  minDateLoading: false,
});

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const MONTH_NAMES = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

function formatDisplay(iso: string): string {
  if (!iso) return "Select a date";
  const [y, m, d] = iso.split("-");
  return `${m}/${d}/${y}`;
}

interface DatePickerProps {
  value: string;
  onChange: (isoDate: string) => void;
  disabled?: boolean;
  maxDate?: string;
  minDate?: string;
  minDateHint?: string;
  minDateLoading?: boolean;
}

const DatePicker: React.FC<DatePickerProps> = ({
  value,
  onChange,
  disabled = false,
  maxDate,
  minDate,
  minDateHint,
  minDateLoading = false,
}) => {
  const today = toIsoDate(new Date());
  const max = maxDate ?? today;

  const [open, setOpen] = useState(false);
  const [calMonth, setCalMonth] = useState<Date>(() => {
    const base = value ? new Date(value + "T00:00:00") : new Date();
    return new Date(base.getFullYear(), base.getMonth(), 1);
  });

  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (value) {
      const d = new Date(value + "T00:00:00");
      setCalMonth(new Date(d.getFullYear(), d.getMonth(), 1));
    }
  }, [value]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node))
        setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const viewYear = calMonth.getFullYear();
  const viewMonth = calMonth.getMonth();
  const maxDateObj = new Date(max + "T00:00:00");
  const minDateObj = minDate ? new Date(minDate + "T00:00:00") : null;

  const minNavYear = minDateObj ? minDateObj.getFullYear() : 1970;
  const minNavMonth = minDateObj ? minDateObj.getMonth() : 0;
  const maxYear = maxDateObj.getFullYear();

  const atMin = viewYear === minNavYear && viewMonth === minNavMonth;
  const atMax = viewYear === maxDateObj.getFullYear() && viewMonth == maxDateObj.getMonth();

  const shiftMonth = (delta: number) => {
    setCalMonth((prev) => {
      const next = new Date(prev.getFullYear(), prev.getMonth() + delta, 1);
      if (minDateObj) {
        const minMonthStart = new Date(minNavYear, minNavMonth, 1);
        if (next < minMonthStart) return prev;
      } else if (next.getFullYear() < 1970) {
        return prev;
      }
      if (toIsoDate(next) > max) return prev;
      return next;
    });
  };

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const firstDow = new Date(viewYear, viewMonth, 1).getDay();
  const cells: Array<number | null> = [
    ...Array(firstDow).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const yearOptions: number[] = [];
  for (let y = maxYear; y >= minNavYear; y--) yearOptions.push(y);

  const dayIso = (day: number) =>
    `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

  const isDayDisabled = (iso: string) => {
    if (iso > max) return true;
    if (minDate && iso < minDate) return true;
    return false;
  };

  return (
    <div className="dp-wrap" ref={wrapRef}>
      <button
        type="button"
        className={`dp-trigger${open ? " dp-open" : ""}${!value ? " dp-empty" : ""}`}
        onClick={() => !disabled && !minDateLoading && setOpen((o) => !o)}
        disabled={disabled || minDateLoading}
        title={minDateLoading ? "Loading earliest available date..." : undefined}
      >
        <svg className="dp-icon" viewBox="0 0 16 16" fill="none">
          <rect
            x="1"
            y="3"
            width="14"
            height="12"
            rx="2"
            stroke="currentColor"
            strokeWidth="1.4"
          />
          <path
            d="M5 1v3M11 1v3M1 7h14"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
        <span className="dp-label">{minDateLoading ? "Loading..." : formatDisplay(value)}</span>
        <span className="dp-chevron">▾</span>
      </button>

      {(minDateLoading || minDateHint) && (
        <div style={{ fontSize: "0.7rem", color:"#64748b", marginTop: "0.2rem" }}>
          {minDateLoading ? "Fetching earliest available date..." : minDateHint}
        </div>
      )}

      {open && (
        <div className="dp-popover">
          {/* Nav */}
          <div className="dp-nav">
            <button
              type="button"
              className="dp-nav-btn"
              onClick={() => shiftMonth(-1)}
              disabled={atMin}
            >
              ‹
            </button>
            <div className="dp-nav-selects">
              <select
                className="dp-select"
                value={viewMonth}
                onChange={(e) =>
                  setCalMonth(new Date(viewYear, Number(e.target.value), 1))
                }
              >
                {MONTH_NAMES.map((name, i) => (
                  <option key={name} value={i}>
                    {name}
                  </option>
                ))}
              </select>
              <select
                className="dp-select"
                value={viewYear}
                onChange={(e) =>
                  setCalMonth(new Date(Number(e.target.value), viewMonth, 1))
                }
              >
                {yearOptions.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              className="dp-nav-btn"
              onClick={() => shiftMonth(1)}
              disabled={atMax}
            >
              ›
            </button>
          </div>
          {/* Weekday labels */}
          <div className="dp-weekdays">
            {WEEKDAYS.map((d) => (
              <div key={d} className="dp-weekday">
                {d}
              </div>
            ))}
          </div>
          {/* Day grid */}
          <div className="dp-days">
            {cells.map((day, i) =>
              day === null ? (
                <div key={`b-${i}`} />
              ) : (
                <button
                  key={dayIso(day)}
                  type="button"
                  className={[
                    "dp-day",
                    dayIso(day) === value ? "dp-day-sel" : "",
                    dayIso(day) === today ? "dp-day-today" : "",
                    isDayDisabled(dayIso(day)) ? "dp-day-dis" : "",
                  ]
                    .join(" ")
                    .trim()}
                  disabled={isDayDisabled(dayIso(day))}
                  onClick={() => {
                    onChange(dayIso(day));
                    setOpen(false);
                  }}
                >
                  {day}
                </button>
              ),
            )}
          </div>
          {/* Today shortcut */}
          <div className="dp-popover-footer">
            <button
              type="button"
              className="dp-today-btn"
              onClick={() => {
                onChange(today);
                setOpen(false);
              }}
            >
              Today
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

interface TickerSearchProps {
  value: string;
  onChange: (ticker: string) => void;
  allStocks: StockOption[];
  disabled: boolean;
}

// Ticker search dropdown component
const TickerSearch: React.FC<TickerSearchProps> = ({
  value,
  onChange,
  allStocks,
  disabled,
}) => {
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
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = query.trim()
    ? allStocks
        .filter(
          (s) =>
            s.ticker.toUpperCase().includes(query.toUpperCase()) ||
            (TICKER_NAMES[s.ticker] || "")
              .toLowerCase()
              .includes(query.toLowerCase()),
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
        className="imp-input"
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
              <span className="imp-ticker-opt-name">
                {TICKER_NAMES[s.ticker] || ""}
              </span>
              {s.close != null && (
                <span className="imp-ticker-opt-price">
                  ${s.close.toFixed(2)}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Main modal component
const ImportPortfolioModal: React.FC<ImportPortfolioMoalProps> = ({
  onClose,
  onSuccess,
}) => {
  const [entries, setEntries] = useState<ImportEntry[]>([emptyEntry()]);
  const [submitting, setSubmitting] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [allStocks, setAllStocks] = useState<StockOption[]>([]);

  const today = toIsoDate(new Date());

  useEffect(() => {
    axios
      .get<StockOption[]>(`${API_BASE}/api/stocks/latest`)
      .then((res) => setAllStocks(res.data.filter((s) => s.close !== null)))
      .catch(() => setAllStocks([]));
  }, []);

  const lookupPrice = async (
    entryId: string,
    ticker: string,
    dateStr: string,
  ) => {
    if (!ticker || !dateStr) return;

    // Start loading state
    setEntries((prev) =>
      prev.map((e) =>
        e.id === entryId
          ? {
              ...e,
              needs_manual_price: false,
              price_found: null,
              price_loading: true,
            }
          : e,
      ),
    );

    try {
      const res = await axios.get(
        `${API_BASE}/api/stocks/${encodeURIComponent(ticker)}/prices`,
        { params: { start_date: dateStr, end_date: dateStr } },
      );

      if (res.data.length > 0) {
        const price = res.data[0].close;
        setEntries((prev) =>
          prev.map((e) =>
            e.id === entryId
              ? {
                  ...e,
                  price_found: price,
                  price_loading: false,
                  needs_manual_price: false,
                  avg_price: price.toFixed(2),
                }
              : e,
          ),
        );
        return;
      }

      // Take the first result — closest trading day on or after the date
      const res2 = await axios.get(
        `${API_BASE}/api/stocks/${encodeURIComponent(ticker)}/prices`,
        { params: { start_date: dateStr } },
      );

      if (res2.data.length > 0) {
        const price = res2.data[0].close;
        setEntries((prev) =>
          prev.map((e) =>
            e.id === entryId
              ? {
                  ...e,
                  price_found: price,
                  price_loading: false,
                  needs_manual_price: false,
                  avg_price: price.toFixed(2),
                }
              : e,
          ),
        );
        return;
      }

      //No data found for this ticker -> manual entry
      setEntries((prev) =>
        prev.map((e) =>
          e.id === entryId
            ? {
                ...e,
                price_found: null,
                price_loading: false,
                needs_manual_price: true,
              }
            : e,
        ),
      );
    } catch {
      setEntries((prev) =>
        prev.map((e) =>
          e.id === entryId
            ? {
                ...e,
                price_found: null,
                price_loading: false,
                needs_manual_price: true,
              }
            : e,
        ),
      );
    }
  };

  const fetchTickerMinDate = async (entryId: string, ticker: string) => {
    if (!ticker) return;
    setEntries((prev) => 
      prev.map((e) => e.id === entryId ? { ...e, minDate: null, minDateLoading: true } : e)
    );
    try {
      const period2 = Math.floor(Date.now() / 1000);
      const url = `${API_BASE}/api/stock-history?ticker=${encodeURIComponent(ticker)}&period1=0&period2=${period2}&interval=1mo`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      const chart = data?.chart?.result?.[0];
      const firstTradeDate = chart?.meta?.firstTradeDate as number | undefined;
      const firstTimestamp = Array.isArray(chart?.timestamp) ? (chart.timestamp[0] as number | undefined) : undefined;
      const firstSeconds = firstTradeDate ?? firstTimestamp;
      let minDate: string | null = null;
      if (typeof firstSeconds === "number" && Number.isFinite(firstSeconds)) {
        const d = new Date(firstSeconds * 1000);
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        minDate = `${y}-${m}-${day}`;
      }
      setEntries((prev) => 
        prev.map((e) => e.id === entryId ? { ...e, minDate, minDateLoading: false } : e)
      );
    } catch {
      setEntries((prev) => 
        prev.map((e) => e.id === entryId ? { ...e, minDate: null, minDateLoading: false } : e)
      );
    }
  };

  const updateEntry = (id: string, field: keyof ImportEntry, value: string) => {
    setEntries((prev) =>
      prev.map((e) =>
        e.id === id
          ? {
              ...e,
              [field]: field === "ticker" ? value.toUpperCase() : value,
              status: "idle",
              error: undefined,
            }
          : e,
      ),
    );
  };

  const addRow = () => setEntries((prev) => [...prev, emptyEntry()]);

  const removeRow = (id: string) => {
    if (entries.length === 1) return;
    setEntries((prev) => prev.filter((e) => e.id !== id));
  };

  const validateEntries = (e: ImportEntry): string | null => {
    if (!e.ticker.trim()) return "Ticker is required";
    const qty = parseFloat(e.quantity);
    if (isNaN(qty) || qty <= 0) return "Quantity must be a positive number";
    if (!e.purchase_date) return "Purchase date is required";
    if (e.minDate && e.purchase_date < e.minDate) {
      const [y, m, d] = e.minDate.split("-")
      return `${e.ticker} was not publicly traded before ${m}/${d}/${y}`;
    }
    if (e.needs_manual_price) {
      const price = parseFloat(e.avg_price);
      if (isNaN(price) || price <= 0)
        return "Enter the price you paid per share";
    }
    if (!e.needs_manual_price && e.price_found === null)
      return "Waiting for price lookup";
    return null;
  };

  const handleImport = async () => {
    setGlobalError(null);

    let hasError = false;
    const validated = entries.map((e) => {
      const err = validateEntries(e);
      if (err) {
        hasError = true;
        return { ...e, status: "error" as const, error: err };
      }
      return e;
    });
    if (hasError) {
      setEntries(validated);
      return;
    }

    setSubmitting(true);
    const token = getToken();
    if (!token) {
      setGlobalError("You must be logged in.");
      setSubmitting(false);
      return;
    }

    const results = await Promise.all(
      entries.map(async (e) => {
        const resolvedPrice = parseFloat(e.avg_price) || e.price_found || 0;
        try {
          await axios.post(
            `${API_BASE}/api/portfolio`,
            {
              ticker: e.ticker.trim(),
              quantity: parseFloat(e.quantity),
              avg_price: resolvedPrice,
              purchase_date: e.purchase_date || null,
            },
            {
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
              },
            },
          );
          return { ...e, status: "saved" as const };
        } catch (err: any) {
          const detail = err.response?.data?.detail;
          const msg =
            typeof detail === "string"
              ? detail
              : Array.isArray(detail)
                ? detail.map((d: any) => d.msg).join(", ")
                : "Failed to import";
          return { ...e, status: "error" as const, error: msg };
        }
      }),
    );

    setEntries(results);
    setSubmitting(false);

    const allSaved = results.every((r) => r.status === "saved");
    if (allSaved) setTimeout(onSuccess, 400);
  };

  const savedCount = entries.filter((e) => e.status === "saved").length;
  const allDone =
    entries.length > 0 && entries.every((e) => e.status === "saved");

  return (
    <div
      className="imp-backdrop"
      onClick={(ev) => ev.target === ev.currentTarget && onClose()}
    >
      <div className="imp-modal">
        {/* Header */}
        <div className="imp-header">
          <div>
            <h2 className="imp-title">Import Your Portfolio</h2>
            <p className="imp-subtitle">
              Add stocks you already own and when you bought them
            </p>
            <p
              style={{
                margin: "6px 0 0",
                fontSize: "0.75rem",
                color: "#475569",
                fontStyle: "italic",
              }}
            >
              *If no price data is found for a date, manual price input will be
              required
            </p>
          </div>
          <button className="imp-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        {/* Column headers */}
        <div className="imp-col-headers">
          <span>Ticker</span>
          <span>Shares Owned</span>
          <span>Purchase Date</span>
          <span>Purchase Price</span>
          <span>Total Cost</span>
          <span></span>
        </div>

        {/* Rows */}
        <div className="imp-rows">
          {entries.map((entry) => {
            const qty = parseFloat(entry.quantity);
            const resolvedPrice =
              parseFloat(entry.avg_price) || entry.price_found || 0;
            const total =
              !isNaN(qty) && qty > 0 && resolvedPrice > 0
                ? qty * resolvedPrice
                : null;
            const isSaved = entry.status === "saved";
            const minDateHint = entry.minDate ? (() => { const [y, m, d] = entry.minDate!.split("-"); return `Earliest: ${m}/${d}/${y}`;})() 
              : undefined;

            return (
              <div
                key={entry.id}
                className={`imp-row ${entry.status === "error" ? "imp-row-error" : ""} ${isSaved ? "imp-row-saved" : ""}`}
              >
                {/* Ticker search */}
                <div className="imp-field imp-field-ticker">
                  <TickerSearch
                    value={entry.ticker}
                    onChange={(val) => {
                      updateEntry(entry.id, "ticker", val);
                      fetchTickerMinDate(entry.id, val);
                      if (entry.purchase_date)
                        lookupPrice(entry.id, val, entry.purchase_date);
                    }}
                    allStocks={allStocks}
                    disabled={isSaved || submitting}
                  />
                </div>
                {/* Quantity */}
                <div className="imp-field">
                  <input
                    className="imp-input"
                    type="number"
                    placeholder="e.g. 10"
                    min="0.0001"
                    step="any"
                    value={entry.quantity}
                    onChange={(e) =>
                      updateEntry(entry.id, "quantity", e.target.value)
                    }
                    disabled={isSaved || submitting}
                  />
                </div>
                {/* Purchase date */}
                <div className="imp-field">
                  <DatePicker
                    value={entry.purchase_date}
                    maxDate={today}
                    minDate={entry.minDate ?? undefined}
                    minDateHint={minDateHint}
                    minDateLoading={entry.minDateLoading}
                    disabled={isSaved || submitting}
                    onChange={(date) => {
                      updateEntry(entry.id, "purchase_date", date);
                      if (entry.ticker)
                        lookupPrice(entry.id, entry.ticker, date);
                    }}
                  />
                </div>
                {/* Price */}
                <div className="imp-field">
                  {entry.price_loading ? (
                    <span style={{ color: "#64748b", fontSize: "0.85rem" }}>
                      Looking up price...
                    </span>
                  ) : entry.price_found !== null ? (
                    // Price found — pre-populated but editable
                    <div className="imp-input-prefix-wrap">
                      <span className="imp-prefix">$</span>
                      <input
                        className="imp-input imp-input-prefixed"
                        type="number"
                        placeholder="Price paid"
                        min="0.01"
                        step="any"
                        value={entry.avg_price}
                        onChange={(e) =>
                          updateEntry(entry.id, "avg_price", e.target.value)
                        }
                        disabled={isSaved}
                      />
                    </div>
                  ) : entry.needs_manual_price ? (
                    // No data found - manual entry
                    <div className="imp-input-prefix-wrap">
                      <span className="imp-prefix">$</span>
                      <input
                        className="imp-input imp-input-prefixed"
                        type="number"
                        placeholder="Price paid"
                        min="0.01"
                        step="any"
                        value={entry.avg_price}
                        onChange={(e) =>
                          updateEntry(entry.id, "avg_price", e.target.value)
                        }
                        disabled={isSaved || submitting}
                      />
                    </div>
                  ) : (
                    // No date entered yet
                    <span style={{ color: "#334155", fontSize: "0.9rem" }}>
                      Enter date first
                    </span>
                  )}
                </div>
                {/* Total cost */}
                <div className="imp-field imp-field-total">
                  {total !== null ? (
                    <span className="imp-total-val">
                      $
                      {total.toLocaleString("en-US", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </span>
                  ) : (
                    <span className="imp-total-empty">-</span>
                  )}
                </div>
                {/* Remove button */}
                <div className="imp-field imp-field-action">
                  {isSaved ? (
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
          <button
            className="imp-add-row-btn"
            onClick={addRow}
            disabled={submitting}
          >
            + Add Another Stock
          </button>
        )}

        {globalError && <p className="imp-global-error">{globalError}</p>}

        {savedCount > 0 && !allDone && (
          <p className="imp-progress">
            {savedCount} of {entries.length} saved — fix errors above to
            continue.
          </p>
        )}

        {/* Footer */}
        <div className="imp-footer">
          <button
            className="imp-cancel-btn"
            onClick={onClose}
            disabled={submitting}
          >
            {allDone ? "Close" : "Cancel"}
          </button>
          {!allDone && (
            <button
              className="imp-confirm-btn"
              onClick={handleImport}
              disabled={submitting || entries.length === 0}
            >
              {submitting ? (
                <>
                  <span className="imp-spinner" />
                  Importing...
                </>
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
