/*
 * AddToPortfolio.tsx
 * Modal for adding shares to a portfolio position.
 * Supports an optional purchase date: when a past date is selected the
 * historical close price is looked up automatically (same logic as the
 * import modal). Falls back to manual price entry when no data is found.
 */
import React, { useState, useEffect } from "react";
import { getToken } from "../utils/auth";
import axios from "axios";
import "./AddToPortfolio.css";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

function toIsoDate(d: Date): string {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
}

const TODAY = toIsoDate(new Date());

interface AddToPortfolioModalProps {
    ticker: string;
    currentPrice: number;
    onClose: () => void;
    onSuccess: () => void;
}

const AddToPortfolioModal: React.FC<AddToPortfolioModalProps> = ({
  ticker,
  currentPrice,
  onClose,
  onSuccess,
}) => {
    const [quantity, setQuantity] = useState<string>("");
    const [purchaseDate, setPurchaseDate] = useState<string>("");
    const [minDate, setMinDate] = useState<string | null>(null);
    const [minDateLoading, setMinDateLoading] = useState(false);
    const [priceLoading, setPriceLoading] = useState(false);
    const [priceForDate, setPriceForDate] = useState<number | null>(null);
    const [needsManualPrice, setNeedsManualPrice] = useState(false);
    const [marketPriceUnavailable, setMarketPriceUnavailable] = useState(false);
    const [manualPrice, setManualPrice] = useState<string>("");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [sharesOutstanding, setSharesOutstanding] = useState<number | null>(null);
    const [currentOwned, setCurrentOwned] = useState<number>(0);

    useEffect(() => {
        const token = getToken();
        Promise.all([
            axios.get(`${API_BASE}/api/stocks/${encodeURIComponent(ticker)}/shares-outstanding`)
                .then(r => setSharesOutstanding(r.data.shares_outstanding ?? null))
                .catch(() => {}),
            token
                ? axios.get(`${API_BASE}/api/portfolio/${encodeURIComponent(ticker)}`, {
                    headers: { Authorization: `Bearer ${token}` },
                  }).then(r => setCurrentOwned(r.data.quantity ?? 0)).catch(() => {})
                : Promise.resolve(),
        ]);
    }, [ticker]);

    useEffect(() => {
        let isActive = true;

        const fetchTickerMinDate = async () => {
            setMinDateLoading(true);
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

                if (!isActive) return;

                if (typeof firstSeconds === "number" && Number.isFinite(firstSeconds)) {
                    const d = new Date(firstSeconds * 1000);
                    const y = d.getFullYear();
                    const m = String(d.getMonth() + 1).padStart(2, "0");
                    const day = String(d.getDate()).padStart(2, "0");
                    setMinDate(`${y}-${m}-${day}`);
                } else {
                    setMinDate(null);
                }
            } catch {
                if (isActive) setMinDate(null);
            } finally {
                if (isActive) setMinDateLoading(false);
            }
        };

        fetchTickerMinDate();

        return () => {
            isActive = false;
        };
    }, [ticker]);

    const lookupPrice = async (dateStr: string) => {
        if (!dateStr || dateStr === TODAY) {
            setPriceForDate(null);
            setNeedsManualPrice(false);
            setMarketPriceUnavailable(false);
            return;
        }
        // dateStr here is already a complete 4-digit-year date (enforced by handleDateChange)
        if (minDate && dateStr < minDate) {
            setPriceForDate(null);
            setNeedsManualPrice(false);
            setMarketPriceUnavailable(false);
            setPriceLoading(false);
            return;
        }
        setPriceLoading(true);
        setPriceForDate(null);
        setNeedsManualPrice(false);
        setMarketPriceUnavailable(false);
        try {
            const res = await axios.get(
                `${API_BASE}/api/stocks/${encodeURIComponent(ticker)}/historical-price`,
                { params: { date: dateStr } },
            );
            if (res.data.close != null) {
                setPriceForDate(res.data.close);
                setMarketPriceUnavailable(false);
            } else {
                setNeedsManualPrice(true);
                setMarketPriceUnavailable(true);
            }
        } catch {
            setNeedsManualPrice(true);
            setMarketPriceUnavailable(true);
        } finally {
            setPriceLoading(false);
        }
    };

    const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const date = e.target.value;
        // Always update state so the field doesn't reset mid-entry
        setPurchaseDate(date);
        setManualPrice("");
        setError(null);
        setMarketPriceUnavailable(false);

        if (!date) return;

        // Only validate min date when the year is fully typed (4 digits, >= 1000).
        // While the user is still entering the year, intermediate browser values
        // like "0198-01-01" would otherwise trigger a false before-IPO error.
        const year = parseInt(date.split("-")[0], 10);
        if (minDate && year >= 1000 && date < minDate) {
            const [y, m, d] = minDate.split("-");
            setError(`${ticker} was not publicly traded before ${m}/${d}/${y}.`);
            setPriceForDate(null);
            setNeedsManualPrice(false);
            return;
        }

        if (year >= 1000) {
            lookupPrice(date);
        }
    };

    // Effective price: historical if date selected, otherwise live current price
    const isHistorical = purchaseDate && purchaseDate !== TODAY;
    const effectivePrice = needsManualPrice
        ? parseFloat(manualPrice)
        : isHistorical
            ? priceForDate ?? 0
            : currentPrice;

    const MIN_SHARES = 0.0001;
    const maxAdditional = sharesOutstanding !== null
        ? Math.max(0, sharesOutstanding - currentOwned)
        : null;
    const parsedQty = parseFloat(quantity);
    const exceedsMax = maxAdditional !== null && !isNaN(parsedQty) && parsedQty > maxAdditional;
    const priceReady = !priceLoading && (!needsManualPrice || (parseFloat(manualPrice) > 0));
    const isValid =
        !isNaN(parsedQty) &&
        parsedQty >= MIN_SHARES &&
        !exceedsMax &&
        priceReady &&
        (!needsManualPrice || parseFloat(manualPrice) > 0);

    const totalCost = isValid && effectivePrice > 0 ? parsedQty * effectivePrice : 0;

    const formatTotalCost = (value: number): string => {
        if (value >= 0.005) return `$${value.toFixed(2)}`;
        return `$${parseFloat(value.toFixed(6))}`;
    };

    const handleSubmit = async () => {
        if (!isValid) {
            if (exceedsMax) {
                setError(`You can add at most ${maxAdditional!.toLocaleString()} shares.`);
            } else if (needsManualPrice && !(parseFloat(manualPrice) > 0)) {
                setError("Enter the price you paid per share.");
            } else {
                setError("Please enter a number of shares of at least 0.0001.");
            }
            return;
        }

        const token = getToken();
        if (!token) {
            setError("You must be logged in to add stocks");
            return;
        }

        setSubmitting(true);
        setError(null);

        try {
            await axios.post(
                `${API_BASE}/api/portfolio`,
                JSON.stringify({
                    ticker,
                    quantity: parsedQty,
                    avg_price: effectivePrice,
                    purchase_date: purchaseDate || null,
                }),
                { headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } }
            );
            onSuccess();
        } catch (err: any) {
            const detail = err.response?.data?.detail;
            let message = "Failed to add to portfolio.";
            if (Array.isArray(detail)) {
                message = detail.map((d: any) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join(", ");
            } else if (typeof detail === "string") {
                message = detail;
            } else if (err.message) {
                message = err.message;
            }
            setError(message);
            setSubmitting(false);
        }
    };

    const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
        if (e.target === e.currentTarget) onClose();
    };

    const minDateHint = minDate
        ? (() => {
            const [y, m, d] = minDate.split("-");
            return `Earliest: ${m}/${d}/${y}`;
        })()
        : null;
    const priceToggleLabel = isHistorical ? "Use average price on day?" : "Use current price?";
    const priceDisplayLabel = needsManualPrice
        ? "Entered Price"
        : isHistorical
            ? "Price on Date"
            : "Current Price";

    return (
        <div className="modal-backdrop" onClick={handleBackdropClick}>
            <div className="modal-container">
                <div className="modal-header">
                    <h2>Add <span className="modal-ticker">{ticker}</span> to Portfolio</h2>
                    <button className="modal-close-btn" onClick={() => onClose()} aria-label="Close">x</button>
                </div>

                <div className="modal-body">
                    {/* Price display */}
                    <div className="modal-price-info">
                        <span className="modal-label">
                            {priceDisplayLabel}
                        </span>
                        {priceLoading ? (
                            <span className="modal-price-loading">Looking up price...</span>
                        ) : (
                            <span className="modal-price">
                                {effectivePrice > 0 ? `$${effectivePrice.toFixed(2)}` : "—"}
                            </span>
                        )}
                    </div>

                    {/* Quantity */}
                    <label className="modal-label" htmlFor="qty-input">Number of Shares</label>
                    <input
                        id="qty-input"
                        className="modal-input"
                        type="number"
                        min="0.0001"
                        max={maxAdditional !== null ? maxAdditional : undefined}
                        step="any"
                        placeholder="e.g. 10"
                        value={quantity}
                        onChange={(e) => {
                            setQuantity(e.target.value);
                            setError(null);
                        }}
                        onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                        autoFocus
                    />
                    {maxAdditional !== null && !exceedsMax && (
                        <p className="modal-max-hint">
                            Max: {maxAdditional.toLocaleString()} shares available
                        </p>
                    )}
                    {exceedsMax && (
                        <p className="modal-error">
                            Exceeds shares outstanding. Max you can add: {maxAdditional!.toLocaleString()}
                        </p>
                    )}

                    {/* Purchase date */}
                    <label className="modal-label" htmlFor="date-input">Purchase Date <span className="modal-label-optional">(optional)</span></label>
                    <input
                        id="date-input"
                        className="modal-input"
                        type="date"
                        min={minDate ?? undefined}
                        max={TODAY}
                        value={purchaseDate}
                        onChange={handleDateChange}
                    />
                    {(minDateLoading || minDateHint) && (
                        <p className="modal-max-hint">
                            {minDateLoading ? "Fetching earliest available date..." : minDateHint}
                        </p>
                    )}
                    <label className="modal-checkbox-row">
                        <input
                            type="checkbox"
                            checked={!needsManualPrice}
                            disabled={marketPriceUnavailable}
                            onChange={(e) => {
                                const useMarketPrice = e.target.checked;
                                setNeedsManualPrice(!useMarketPrice);
                                if (useMarketPrice) {
                                    setError(null);
                                }
                            }}
                        />
                        <span>{priceToggleLabel}</span>
                    </label>
                    {isHistorical && purchaseDate && (
                        <p className="modal-split-note">
                            Prices are split-adjusted. If {ticker} has split since this date, enter your current (post-split) share count.
                        </p>
                    )}

                    {/* Manual price entry when no data found */}
                    {needsManualPrice && (
                        <>
                            <label className="modal-label" htmlFor="manual-price-input">
                                Price Paid Per Share
                            </label>
                            <div className="modal-prefix-wrap">
                                <span className="modal-prefix">$</span>
                                <input
                                    id="manual-price-input"
                                    className="modal-input modal-input-prefixed"
                                    type="number"
                                    min="0.0001"
                                    step="any"
                                    placeholder="Enter price paid"
                                    value={manualPrice}
                                    onChange={(e) => { setManualPrice(e.target.value); setError(null); }}
                                />
                            </div>
                            <p className="modal-max-hint">
                                {marketPriceUnavailable
                                    ? "No price data found for this date- enter manually."
                                    : " "}
                            </p>
                        </>
                    )}

                    {/* Total cost preview */}
                    {isValid && totalCost > 0 && (
                        <div className="modal-cost-preview">
                            <span className="modal-label">Total Cost</span>
                            <span className="modal-cost-value">{formatTotalCost(totalCost)}</span>
                        </div>
                    )}
                    {error && <p className="modal-error">{error}</p>}
                </div>

                <div className="modal-footer">
                    <button className="modal-cancel-btn" onClick={() => onClose()} disabled={submitting}>
                        Cancel
                    </button>
                    <button
                        className="modal-confirm-btn"
                        onClick={handleSubmit}
                        disabled={!isValid || submitting}
                    >
                        {submitting ? "Adding..." : "Add to Portfolio"}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default AddToPortfolioModal;
