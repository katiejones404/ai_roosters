from __future__ import annotations

import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

import psycopg2
from pydantic import BaseModel

# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------

logger = logging.getLogger("sentiment_snapshot_pipeline")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)

# --------------------------------------------------------------------------------------
# DB
# --------------------------------------------------------------------------------------


def get_dsn() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db",
    )


# --------------------------------------------------------------------------------------
# Artifacts
# --------------------------------------------------------------------------------------


class SnapshotRequest(BaseModel):
    ticker: Optional[str] = None


class SnapshotResult(BaseModel):
    num_written: int
    num_skipped: int


# --------------------------------------------------------------------------------------
# GPT Helper
# --------------------------------------------------------------------------------------


def generate_gpt_explanations(row: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    ALWAYS returns keys: d30, d120, d360 (values may be None).

    Uses OpenAI Responses API over HTTP (no openai package required).
    Enforces strict JSON via Structured Outputs (text.format json_schema).
    """

    default_out: Dict[str, Optional[str]] = {"d30": None, "d120": None, "d360": None}

    if os.getenv("ENABLE_GPT_EXPLANATIONS", "0") != "1":
        return default_out

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        logger.warning("OPENAI_API_KEY missing, skipping GPT stage.")
        return default_out

    import json
    import time
    import re
    import requests

    model = os.getenv("GPT_EXPL_MODEL", "gpt-4o-mini")

    prompt = (
        "You are a finance dashboard assistant.\n"
        "Write short explanations that summarize how article sentiment relates to 30-day / 120-day / 360-day horizons.\n"
        "Do NOT give investment advice (no buy/sell/hold). Avoid hype and certainty words.\n"
        "Each value must be 1–2 sentences, cautious if uncertain.\n\n"
        f"Ticker: {row.get('ticker')}\n"
        f"Snapshot date: {row.get('snapshot_date')}\n\n"
        "Returns:\n"
        f"- 30-day: {row.get('return_30d')}\n"
        f"- 120-day: {row.get('return_120d')}\n"
        f"- 360-day: {row.get('return_360d')}\n\n"
        "Articles:\n"
        f"- total: {row.get('num_articles')}\n"
        f"- positive: {row.get('num_pos_articles')}\n"
        f"- negative: {row.get('num_neg_articles')}\n"
    )

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "d30": {"type": ["string", "null"]},
            "d120": {"type": ["string", "null"]},
            "d360": {"type": ["string", "null"]},
        },
        "required": ["d30", "d120", "d360"],
    }

    payload: Dict[str, Any] = {
        "model": model,
        "input": prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "sentiment_explanations",  # REQUIRED
                "strict": True,
                "schema": schema,
            }
        },
    }

    def _extract_output_text(resp_json: Dict[str, Any]) -> str:
        t = (resp_json.get("output_text") or "").strip()
        if t:
            return t

        out = resp_json.get("output")
        if isinstance(out, list):
            for item in out:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "message":
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "output_text" and isinstance(c.get("text"), str):
                        return c["text"].strip()
                    if isinstance(c.get("text"), str):
                        return c["text"].strip()
        return ""

    def _safe_json_loads(s: str) -> Optional[Dict[str, Any]]:
        s = (s or "").strip()
        if not s:
            return None
        if not s.startswith("{"):
            m = re.search(r"\{.*\}", s, flags=re.DOTALL)
            if m:
                s = m.group(0).strip()
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Retry for transient failures
    for attempt in range(1, 4):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=45)

            if r.status_code >= 300:
                body_preview = (r.text or "")[:600]
                logger.warning(f"OpenAI error {r.status_code}: {body_preview}")
                return default_out

            try:
                resp_json = r.json()
            except Exception:
                body_preview = (r.text or "")[:600]
                logger.warning(f"OpenAI returned non-JSON body (first 600 chars): {body_preview}")
                return default_out

            text_out = _extract_output_text(resp_json)
            parsed = _safe_json_loads(text_out)

            if not parsed:
                logger.warning(f"GPT returned unparsable/empty output_text: {text_out[:250]!r}")
                return default_out

            return {
                "d30": parsed.get("d30"),
                "d120": parsed.get("d120"),
                "d360": parsed.get("d360"),
            }

        except requests.exceptions.RequestException as e:
            logger.warning(f"GPT request failed (attempt {attempt}/3): {e}")
            if attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            return default_out
        except Exception as e:
            logger.warning(f"GPT call failed: {e}")
            return default_out

    return default_out


# --------------------------------------------------------------------------------------
# Main Aggregator Logic
# --------------------------------------------------------------------------------------


def _fetch_rows_needing_gpt(
    cur,
    ticker_filter: Optional[str],
    mode: str,
    limit_rows: int,
) -> List[Tuple[Any, ...]]:
    """
    mode:
      - "latest"   -> latest snapshot per ticker (your current behavior)
      - "backfill" -> any rows missing GPT, newest first, limited by limit_rows
    """
    params: List[Any] = []
    extra_and = ""
    if ticker_filter:
        extra_and = "AND ticker ILIKE %s"
        params.append(f"%{ticker_filter}%")

    if mode == "backfill":
        # Fill any missing GPT fields, newest first (can be many rows)
        cur.execute(
            f"""
            SELECT
                ticker,
                snapshot_date,
                return_30d,
                return_120d,
                return_360d,
                num_articles,
                num_pos_articles,
                num_neg_articles
            FROM sentiment_snapshots
            WHERE (
                gpt_expl_30d IS NULL
                OR gpt_expl_120d IS NULL
                OR gpt_expl_360d IS NULL
            )
            {extra_and}
            ORDER BY snapshot_date DESC NULLS LAST, ticker
            LIMIT %s;
            """,
            params + [limit_rows],
        )
        return cur.fetchall()

    # Default: latest snapshot per ticker missing GPT
    cur.execute(
        f"""
        SELECT DISTINCT ON (ticker)
            ticker,
            snapshot_date,
            return_30d,
            return_120d,
            return_360d,
            num_articles,
            num_pos_articles,
            num_neg_articles
        FROM sentiment_snapshots
        WHERE (
            gpt_expl_30d IS NULL
            OR gpt_expl_120d IS NULL
            OR gpt_expl_360d IS NULL
        )
        {extra_and}
        ORDER BY ticker, snapshot_date DESC;
        """,
        params,
    )
    return cur.fetchall()


def run_pipeline(request: SnapshotRequest) -> SnapshotResult:
    logger.info("Running sentiment snapshot aggregator")

    dsn = get_dsn()
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    mode = os.getenv("GPT_FILL_MODE", "latest").strip().lower()  # latest|backfill
    limit_rows = int(os.getenv("GPT_BACKFILL_LIMIT", "200"))

    rows = _fetch_rows_needing_gpt(cur, request.ticker, mode=mode, limit_rows=limit_rows)
    logger.info(f"Rows needing GPT ({mode}): {len(rows)}")

    written = 0
    skipped = 0
    model_name = os.getenv("GPT_EXPL_MODEL", "gpt-4o-mini")

    for (
        ticker,
        snapshot_date,
        r30,
        r120,
        r360,
        num_articles,
        num_pos,
        num_neg,
    ) in rows:
        row_data = {
            "ticker": ticker,
            "snapshot_date": str(snapshot_date),
            "return_30d": r30,
            "return_120d": r120,
            "return_360d": r360,
            "num_articles": num_articles,
            "num_pos_articles": num_pos,
            "num_neg_articles": num_neg,
        }

        expl = generate_gpt_explanations(row_data)

        # Only write + count as updated if we actually got text
        if not (expl.get("d30") and expl.get("d120") and expl.get("d360")):
            logger.warning(f"Skipping DB update for {ticker} {snapshot_date}: GPT output incomplete/empty.")
            skipped += 1
            continue

        cur.execute(
            """
            UPDATE sentiment_snapshots
            SET
                gpt_expl_30d = COALESCE(%s, gpt_expl_30d),
                gpt_expl_120d = COALESCE(%s, gpt_expl_120d),
                gpt_expl_360d = COALESCE(%s, gpt_expl_360d),
                gpt_model = %s,
                gpt_generated_at = %s
            WHERE ticker = %s
              AND snapshot_date = %s;
            """,
            (
                expl.get("d30"),
                expl.get("d120"),
                expl.get("d360"),
                model_name,
                datetime.utcnow(),
                ticker,
                snapshot_date,
            ),
        )

        written += 1

    conn.commit()
    cur.close()
    conn.close()

    logger.info(f"Finished. Updated {written} snapshots. Skipped {skipped}.")
    return SnapshotResult(num_written=written, num_skipped=skipped)


# --------------------------------------------------------------------------------------
# Entry
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    req = SnapshotRequest(ticker=os.getenv("AGG_TICKER") or None)
    run_pipeline(req)