/*
 * AddToPortfolio.tsx
 * Modal component for adding a new stock position to the user's portfolio,
 * with fields for ticker, quantity, and average purchase price.
 */
import React, { useState, useEffect } from "react";
import { getToken } from "../utils/auth";
import axios from "axios";
import "./AddToPortfolio.css";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

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

    const MIN_SHARES = 0.0001;
    const maxAdditional = sharesOutstanding !== null
        ? Math.max(0, sharesOutstanding - currentOwned)
        : null;
    const parsedQty = parseFloat(quantity);
    const exceedsMax = maxAdditional !== null && !isNaN(parsedQty) && parsedQty > maxAdditional;
    const isValid = !isNaN(parsedQty) && parsedQty >= MIN_SHARES && !exceedsMax;
    const totalCost = isValid ? parsedQty * currentPrice : 0;

    const formatTotalCost = (value: number): string => {
        if (value >= 0.005) return `$${value.toFixed(2)}`;
        return `$${parseFloat(value.toFixed(6))}`;
    };

    const handleSubmit = async () => {
        if (!isValid) {
            if (maxAdditional !== null && parsedQty > maxAdditional) {
                setError(`You can add at most ${maxAdditional.toLocaleString()} shares (shares outstanding minus what you already own).`);
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

        try{
            await axios.post(
                `${API_BASE}/api/portfolio`,
                JSON.stringify({ticker, quantity: parsedQty, avg_price: currentPrice}),
                { headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } }
            );
            onSuccess();
        } catch (err: any) {
            console.error("Error adding to portfolio:", err.response?.data);
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

    return (
        <div className="modal-backdrop" onClick={handleBackdropClick}>
            <div className="modal-container">
                <div className="modal-header">
                    <h2>Add <span className="modal-ticker">{ticker}</span> to Portfolio</h2>
                    <button className="modal-close-btn" onClick={() => onClose()} aria-label="Close">x</button>
                </div>

                <div className="modal-body">
                    <div className="modal-price-info">
                        <span className="modal-label">Current Price</span>
                        <span className="modal-price">${currentPrice.toFixed(2)}</span>
                    </div>

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

                    {isValid && (
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