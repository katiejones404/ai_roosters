import { useEffect, useMemo, useRef, useState } from "react";
import "./whatif.css";

const STOCKS = [
  "AAL",
  "AAPL",
  "ALK",
  "AMC",
  "AMD",
  "AMZN",
  "AXP",
  "BAC",
  "BHP",
  "CCL",
  "COIN",
  "COP",
  "CSX",
  "DAL",
  "EA",
  "ENPH",
  "F",
  "FCX",
  "GOOG",
  "GOOGL",
  "INTC",
  "KSS",
  "MARA",
  "META",
  "MRK",
  "MSFT",
  "MU",
  "NFLX",
  "NKE",
  "NTAP",
  "NVDA",
  "NVS",
  "PLTR",
  "PLUG",
  "RIVN",
  "SNAP",
  "SOFI",
  "T",
  "TSLA",
  "XOM",
];

interface Result {
  ticker: string;
  shares: number;
  startPrice: number;
  endPrice: number;
  invested: number;
  currentValue: number;
  gain: number;
  pctReturn: number;
  annualized: number;
  years: string;
}

const MIN_DATE = "1970-01-01";
const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function toIsoDate(dateObj: Date) {
  const year = dateObj.getFullYear();
  const month = String(dateObj.getMonth() + 1).padStart(2, "0");
  const day = String(dateObj.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseIsoDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function formatUiDate(iso: string) {
  if (!iso) return "mm/dd/yyyy";
  const [y, m, d] = iso.split("-");
  return `${m}/${d}/${y}`;
}

function parseUiDate(ui: string) {
  const match = ui.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!match) return null;

  const month = Number(match[1]);
  const day = Number(match[2]);
  const year = Number(match[3]);
  const candidate = new Date(year, month - 1, day);

  if (
    candidate.getFullYear() !== year ||
    candidate.getMonth() !== month - 1 ||
    candidate.getDate() !== day
  ) {
    return null;
  }

  return toIsoDate(candidate);
}

function formatTypingDate(raw: string) {
  const digits = raw.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

export default function WhatIfCalculator() {
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("");
  const [date, setDate] = useState("");
  const [dateInput, setDateInput] = useState("");
  const [tickerMinDate, setTickerMinDate] = useState<string | null>(null);
  const [isLoadingTickerMinDate, setIsLoadingTickerMinDate] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isCalendarOpen, setIsCalendarOpen] = useState(false);

  const today = toIsoDate(new Date());
  const minDate = tickerMinDate ?? MIN_DATE;

  const todayDate = useMemo(() => parseIsoDate(today), [today]);
  const minDateObj = useMemo(() => parseIsoDate(minDate), [minDate]);

  const clampCalendarMonth = (candidate: Date) => {
    const minMonth = new Date(minDateObj.getFullYear(), minDateObj.getMonth(), 1);
    const maxMonth = new Date(todayDate.getFullYear(), todayDate.getMonth(), 1);

    if (candidate < minMonth) return minMonth;
    if (candidate > maxMonth) return maxMonth;
    return candidate;
  };

  const [calendarMonth, setCalendarMonth] = useState<Date>(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const calendarRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isCalendarOpen) return;

    const onDocumentClick = (event: MouseEvent) => {
      if (!calendarRef.current) return;
      if (!calendarRef.current.contains(event.target as Node)) {
        setIsCalendarOpen(false);
      }
    };

    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsCalendarOpen(false);
      }
    };

    document.addEventListener("mousedown", onDocumentClick);
    document.addEventListener("keydown", onEscape);

    return () => {
      document.removeEventListener("mousedown", onDocumentClick);
      document.removeEventListener("keydown", onEscape);
    };
  }, [isCalendarOpen]);

  useEffect(() => {
    if (!ticker) {
      setTickerMinDate(null);
      setIsLoadingTickerMinDate(false);
      return;
    }

    const controller = new AbortController();

    const fetchTickerMinDate = async () => {
      setIsLoadingTickerMinDate(true);

      try {
        const period2 = Math.floor(Date.now() / 1000);
        const url = `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}/api/stock-history?ticker=${ticker}&period1=0&period2=${period2}&interval=1mo`;
        const res = await fetch(url, { signal: controller.signal });
        if (!res.ok) throw new Error("Could not load ticker history.");

        const data = await res.json();
        const chart = data?.chart?.result?.[0];
        const firstTradeDate = chart?.meta?.firstTradeDate as number | undefined;
        const firstTimestamp = Array.isArray(chart?.timestamp)
          ? (chart.timestamp[0] as number | undefined)
          : undefined;
        const firstSeconds = firstTradeDate ?? firstTimestamp;

        if (typeof firstSeconds === "number" && Number.isFinite(firstSeconds)) {
          const discoveredMinDate = toIsoDate(new Date(firstSeconds * 1000));
          setTickerMinDate(discoveredMinDate < MIN_DATE ? MIN_DATE : discoveredMinDate);
        } else {
          setTickerMinDate(MIN_DATE);
        }
      } catch (err: any) {
        if (err.name === "AbortError") return;
        setTickerMinDate(MIN_DATE);
      } finally {
        if (!controller.signal.aborted) {
          setIsLoadingTickerMinDate(false);
        }
      }
    };

    fetchTickerMinDate();

    return () => {
      controller.abort();
    };
  }, [ticker]);

  useEffect(() => {
    if (!ticker || !tickerMinDate) return;

    if (date && date < tickerMinDate) {
      setDateAndReset(tickerMinDate);
      return;
    }

    if (dateInput) {
      const parsedInput = parseUiDate(dateInput);
      if (parsedInput && parsedInput < tickerMinDate) {
        setDateAndReset(tickerMinDate);
      }
    }
  }, [ticker, tickerMinDate, date, dateInput]);

  const clampDate = (raw: string) => {
    if (!raw) return raw;
    if (raw < minDate) return minDate;
    if (raw > today) return today;
    return raw;
  };

  const setDateAndReset = (nextDate: string) => {
    const bounded = clampDate(nextDate);
    setDate(bounded);
    setDateInput(formatUiDate(bounded));
    setResult(null);
    setError("");
  };

  const openCalendar = () => {
    if (!ticker || isLoadingTickerMinDate) return;
    const typedDate = parseUiDate(dateInput);
    const base = date
      ? parseIsoDate(date)
      : typedDate
        ? parseIsoDate(typedDate)
        : todayDate;
    setCalendarMonth(clampCalendarMonth(new Date(base.getFullYear(), base.getMonth(), 1)));
    setIsCalendarOpen(true);
  };

  const applyTypedDate = () => {
    if (!ticker) return;
    if (!dateInput.trim()) {
      setDate("");
      setResult(null);
      setError("");
      return;
    }

    const parsed = parseUiDate(dateInput);
    if (!parsed) {
      setDate("");
      setResult(null);
      setError("Please enter date as MM/DD/YYYY.");
      return;
    }

    setDateAndReset(parsed);
  };

  const shiftMonth = (delta: number) => {
    setCalendarMonth((prev) =>
      clampCalendarMonth(new Date(prev.getFullYear(), prev.getMonth() + delta, 1)),
    );
  };

  const viewYear = calendarMonth.getFullYear();
  const viewMonth = calendarMonth.getMonth();
  const monthFirst = new Date(viewYear, viewMonth, 1);
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const leadingBlankDays = monthFirst.getDay();

  const dayCells: Array<Date | null> = [];
  for (let i = 0; i < leadingBlankDays; i += 1) {
    dayCells.push(null);
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    dayCells.push(new Date(viewYear, viewMonth, day));
  }
  while (dayCells.length % 7 !== 0) {
    dayCells.push(null);
  }

  const minYear = minDateObj.getFullYear();
  const maxYear = todayDate.getFullYear();
  const yearOptions = [];
  for (let y = maxYear; y >= minYear; y -= 1) {
    yearOptions.push(y);
  }

  const atMinMonth =
    viewYear === minDateObj.getFullYear() && viewMonth === minDateObj.getMonth();
  const atMaxMonth =
    viewYear === todayDate.getFullYear() && viewMonth === todayDate.getMonth();

  const calculate = async () => {
    let effectiveDate = date;
    if (dateInput.trim()) {
      const parsedTypedDate = parseUiDate(dateInput);
      if (!parsedTypedDate) {
        setError("Please enter date as MM/DD/YYYY.");
        return;
      }
      effectiveDate = clampDate(parsedTypedDate);
      if (effectiveDate !== date) {
        setDate(effectiveDate);
        setDateInput(formatUiDate(effectiveDate));
      }
    }

    if (!ticker || !shares || !effectiveDate) {
      setError("Please fill in all fields.");
      return;
    }
    const numShares = parseFloat(shares);
    if (isNaN(numShares) || numShares <= 0) {
      setError("Shares must be greater than 0.");
      return;
    }
    if (effectiveDate >= today) {
      setError("Please choose a date in the past.");
      return;
    }

    setError("");
    setLoading(true);
    setResult(null);

    try {
      const startDate = new Date(effectiveDate);
      const endDate = new Date();
      const period1 = Math.floor(startDate.getTime() / 1000);
      const period2 = Math.floor(endDate.getTime() / 1000);

      const url = `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}/api/stock-history?ticker=${ticker}&period1=${period1}&period2=${period2}&interval=1mo`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Market data request failed.");
      const data = await res.json();

      const chart = data?.chart?.result?.[0];
      if (!chart) throw new Error("No data found for that ticker.");

      const closes: (number | null)[] = chart.indicators.quote[0].close;
      const startPrice = closes.find((p) => p != null) as number;
      const endPrice = [...closes].reverse().find((p) => p != null) as number;

      if (!startPrice || !endPrice) throw new Error("Price data unavailable.");

      const invested = numShares * startPrice;
      const currentValue = numShares * endPrice;
      const gain = currentValue - invested;
      const pctReturn = ((endPrice - startPrice) / startPrice) * 100;
      const years =
        (endDate.getTime() - startDate.getTime()) /
        (1000 * 60 * 60 * 24 * 365.25);
      const annualized = (Math.pow(endPrice / startPrice, 1 / years) - 1) * 100;

      setResult({
        ticker,
        shares: numShares,
        startPrice,
        endPrice,
        invested,
        currentValue,
        gain,
        pctReturn,
        annualized,
        years: years.toFixed(1),
      });
    } catch (err: any) {
      setError(
        err.message === "Failed to fetch"
          ? "Could not reach market data. Check your network or backend proxy."
          : err.message,
      );
    } finally {
      setLoading(false);
    }
  };

  const fmt = (n: number) =>
    n.toLocaleString("en-US", { style: "currency", currency: "USD" });
  const fmtPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

  return (
    <div className="wi-section">
      <div className="wi-section-header">
        <h2 className="wi-section-title">What If I Invested?</h2>
        <p className="wi-section-sub">
          Pick a stock, shares, and a past date. See what it&apos;s worth today!
        </p>
      </div>

      <div className="wi-form-card">
        <div className="wi-form-row">
          <div className="wi-field">
            <label className="wi-label">Stock</label>
            <select
              className="wi-select"
              value={ticker}
              onChange={(e) => {
                setTicker(e.target.value);
                setDate("");
                setDateInput("");
                setIsCalendarOpen(false);
                setResult(null);
                setError("");
              }}
            >
              <option value="">Select a stock...</option>
              {STOCKS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="wi-field">
            <label className="wi-label">Number of Shares</label>
            <input
              className="wi-input"
              type="number"
              placeholder="e.g. 10"
              value={shares}
              onChange={(e) => {
                setShares(e.target.value);
                setResult(null);
                setError("");
              }}
              min="0.0001"
              step="any"
            />
          </div>

          <div className="wi-field">
            <label className="wi-label">Date of Investment</label>
            <div className="wi-date-wrap" ref={calendarRef}>
              <div className="wi-date-input-wrap">
                <input
                  className="wi-input wi-date-text-input"
                  type="text"
                  inputMode="numeric"
                  placeholder={
                    !ticker
                      ? "Select stock first"
                      : isLoadingTickerMinDate
                        ? "Loading earliest date..."
                        : "mm/dd/yyyy"
                  }
                  value={dateInput}
                  onChange={(e) => {
                    setDateInput(formatTypingDate(e.target.value));
                    setResult(null);
                    if (error) setError("");
                  }}
                  onBlur={applyTypedDate}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      applyTypedDate();
                    }
                  }}
                  disabled={!ticker || isLoadingTickerMinDate}
                  aria-label="Date of investment in MM/DD/YYYY format"
                />
                <button
                  type="button"
                  className="wi-date-picker-btn"
                  onClick={() => {
                    if (isCalendarOpen) {
                      setIsCalendarOpen(false);
                      return;
                    }
                    openCalendar();
                  }}
                  disabled={!ticker || isLoadingTickerMinDate}
                  aria-expanded={isCalendarOpen}
                  aria-label="Open calendar"
                >
                  <span className="wi-date-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M7 2V5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                      <path d="M17 2V5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                      <path d="M3 9H21" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                      <rect x="3" y="5" width="18" height="16" rx="3" stroke="currentColor" strokeWidth="2"/>
                    </svg>
                  </span>
                </button>
              </div>

              {isCalendarOpen && (
                <div className="wi-calendar-popover">
                  <div className="wi-calendar-header">
                    <button
                      type="button"
                      className="wi-month-nav"
                      onClick={() => shiftMonth(-1)}
                      disabled={atMinMonth}
                      aria-label="Previous month"
                    >
                      &lt;
                    </button>

                    <div className="wi-calendar-selects">
                      <select
                        className="wi-calendar-select"
                        value={viewMonth}
                        onChange={(e) => {
                          const nextMonth = Number(e.target.value);
                          setCalendarMonth(
                            clampCalendarMonth(new Date(viewYear, nextMonth, 1)),
                          );
                        }}
                        aria-label="Select month"
                      >
                        {MONTH_NAMES.map((monthName, idx) => (
                          <option key={monthName} value={idx}>
                            {monthName}
                          </option>
                        ))}
                      </select>

                      <select
                        className="wi-calendar-select"
                        value={viewYear}
                        onChange={(e) => {
                          const nextYear = Number(e.target.value);
                          setCalendarMonth(
                            clampCalendarMonth(new Date(nextYear, viewMonth, 1)),
                          );
                        }}
                        aria-label="Select year"
                      >
                        {yearOptions.map((yearOption) => (
                          <option key={yearOption} value={yearOption}>
                            {yearOption}
                          </option>
                        ))}
                      </select>
                    </div>

                    <button
                      type="button"
                      className="wi-month-nav"
                      onClick={() => shiftMonth(1)}
                      disabled={atMaxMonth}
                      aria-label="Next month"
                    >
                      &gt;
                    </button>
                  </div>

                  <div className="wi-weekdays-row">
                    {WEEKDAYS.map((weekday) => (
                      <div key={weekday} className="wi-weekday-cell">
                        {weekday}
                      </div>
                    ))}
                  </div>

                  <div className="wi-days-grid">
                    {dayCells.map((dayDate, idx) => {
                      if (!dayDate) {
                        return <div key={`blank-${idx}`} className="wi-day-empty" aria-hidden="true" />;
                      }

                      const dayIso = toIsoDate(dayDate);
                      const isDisabled = dayIso < minDate || dayIso > today;
                      const isSelected = dayIso === date;

                      return (
                        <button
                          key={dayIso}
                          type="button"
                          className={`wi-day-btn${isSelected ? " selected" : ""}`}
                          disabled={isDisabled}
                          onClick={() => {
                            setDateAndReset(dayIso);
                            setIsCalendarOpen(false);
                          }}
                        >
                          {dayDate.getDate()}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

          <button
            className="wi-calc-btn"
            onClick={calculate}
            disabled={loading}
          >
            {loading ? "Fetching..." : "Calculate"}
          </button>
        </div>
        {ticker && tickerMinDate && !isLoadingTickerMinDate && (
          <p className="wi-date-hint">
            Earliest available date for {ticker}: {formatUiDate(tickerMinDate)}
          </p>
        )}
        {error && <p className="wi-error">{error}</p>}
      </div>

      {result && (
        <div className="wi-result-grid">
          <div
            className={`wi-result-main ${result.gain >= 0 ? "positive" : "negative"}`}
          >
            <div className="wi-result-label">Current Value (live price)</div>
            <div className="wi-result-big">{fmt(result.currentValue)}</div>
            <div
              className={`wi-result-change ${result.gain >= 0 ? "positive" : "negative"}`}
            >
              {result.gain >= 0 ? "^" : "v"} {fmt(Math.abs(result.gain))} (
              {fmtPct(result.pctReturn)})
            </div>
            <div className="wi-result-sub">
              {result.shares} shares of {result.ticker} bought for {" "}
              {fmt(result.invested)} {result.years} years ago
            </div>
          </div>

          <div className="wi-stats-grid">
            <div className="wi-stat-box">
              <div className="wi-stat-label">Shares</div>
              <div className="wi-stat-val">{result.shares}</div>
            </div>
            <div className="wi-stat-box">
              <div className="wi-stat-label">Price Then</div>
              <div className="wi-stat-val">{fmt(result.startPrice)}</div>
            </div>
            <div className="wi-stat-box">
              <div className="wi-stat-label">Price Now</div>
              <div className="wi-stat-val">{fmt(result.endPrice)}</div>
            </div>
            <div className="wi-stat-box">
              <div className="wi-stat-label">Annualized</div>
              <div
                className={`wi-stat-val ${result.annualized >= 0 ? "positive" : "negative"}`}
              >
                {fmtPct(result.annualized)}/yr
              </div>
            </div>
          </div>

          <div className="wi-verdict">
            {result.gain >= 0
              ? `Your ${result.shares} shares of ${result.ticker} (bought for ${fmt(result.invested)}) would be worth ${fmt(result.currentValue)} today, a ${fmtPct(result.pctReturn)} gain over ${result.years} years.`
              : `Your ${result.shares} shares of ${result.ticker} (bought for ${fmt(result.invested)}) would be worth ${fmt(result.currentValue)} today, a ${fmtPct(result.pctReturn)} loss over ${result.years} years.`}
          </div>
        </div>
      )}
    </div>
  );
}
