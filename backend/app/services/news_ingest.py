#!/usr/bin/env python3
#Current article ingestion as of 1/25/2026, not optimized or integrated with current pipeline
#Gets top articles_per_year with relevant keywords and source domains

#TODO: make args parameter to pass in filters for stocks so that only articles about relevant stocks are passed
"""
news_ingest.py - fast GDELT GKG ingestion with improved title heuristics.

Outputs CSV columns:
  published_at, title, description, url, inserted_at

Usage (example):
  python news_ingest.py --output news_articles.csv --years 2023 --articles-per-year 10 --files-per-year 2 --max-workers 3 --verbose
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import math
import os
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# ---------------- default settings for CLI ----------------
ARTICLES_PER_YEAR_DEFAULT = 100
FILES_PER_YEAR_SAMPLE_DEFAULT = 2
YEARS_DEFAULT = [2023, 2024]


#keywords, not optimized
#TODO: optimize keywords
KEYWORDS_DEFAULT = [
    "stock", "stocks", "market", "markets", "equities", "equity",
    "share", "shares", "ipo", "earnings", "investor", "investment",
    "dow", "nasdaq", "s&p 500", "sp500", "djia", "bond", "bonds", 
    "revenue", "profit", "trading", "ticker", "portfolio",
    "hedge fund", "mutual fund", "etf", "bull", "bear",
    "dividend", "yield", "valuation", "buyback", "merger",
    "acquisition", "m&a", "quarter", "quarterly",
    "wallstreet", "wall street", "nyse", "financial",
]
#will be added to later
#TODO: optimize domains and add targeted domains (WSJ, New York Post, stock websites, etc)
SOURCE_DOMAINS_DEFAULT: List[str] = [
    "wsj.com", "bloomberg.com", "reuters.com", "ft.com",
    "cnbc.com", "marketwatch.com", "investing.com",
    "seekingalpha.com", "fool.com", "barrons.com",
    "forbes.com", "businessinsider.com", "yahoo.com/finance",
    "economist.com", "nytimes.com/business", "thestreet.com"
]

# base host (no gdeltv2 suffix)
GDELT_BASE = "http://data.gdeltproject.org/"
MASTERFILELIST_URL = urljoin(GDELT_BASE, "gdeltv2/masterfilelist.txt")

# Base data directory (two levels up, then /data)
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/"))
MASTERFILELIST_CACHE = os.path.join(DATA_DIR, "masterfilelist.txt")
DEFAULT_OUTPUT = os.path.join(DATA_DIR, "news_articles.csv")
GDELT_CACHE_DIR = os.path.join(DATA_DIR, "gdelt_cache")
os.makedirs(GDELT_CACHE_DIR, exist_ok=True)


# -------------- util --------------
#Return the current time with a UTC timezone, used for 'inserted_at' CSV field 
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
#Substring based keyword matcher
def keyword_match(text: str, keywords: List[str]) -> bool: #compare the text to the list of keywords
    #Substring based keyword matcher with word boundary awarenes
    if not text:
        return False
    t = text.lower()
    for k in keywords:
        k_lower = k.lower()
        # Check for word boundaries to reduce false positives (very common and causes a lot of slowness)
        if len(k_lower.split()) == 1:
            # Single word, check word boundaries
            pattern = r'\b' + re.escape(k_lower) + r'\b'
            if re.search(pattern, t):
                return True
        else:
            # Multi-word phrase, simple substring match
            if k_lower in t:
                return True
    return False
#use later when domains are optimized
#Filter a url by prescence of one of the source_domains
def domain_match(url: str, source_domains: List[str]) -> bool: #returns true if source_domains is empty or any domain substring appears in the URL
    if not source_domains:
        return True
    try:
        host = urlparse(url).netloc.lower()
        return any(d.lower() in host for d in source_domains)
    except Exception:
        return False

# ---------------- masterfilelist helpers ----------------
def extract_gkg_path_from_line(line: str) -> Optional[str]:
    #parse a single like from GDELT file list and extract a gkg file token
    #returns the first substring that ends with '.gkg.csv.zip'
    m = re.search(r'(\S*?\.gkg\.csv\.zip)', line, flags=re.IGNORECASE)
    if m:
        return m.group(1) #returns the matched substring or full URL or None if the line does not contain a GKG file path
    return None

#Download and cache the GDELT masterfilelist with every published file
#if a local cache exists and force_refresh is false, read from cache
#otherwise attempt an HTTP GET to MASTERFILELIST_URL and write the response
#returns a list of raw lines extracfed but only after extracting the gkg path tokens in the loop
def download_masterfilelist(cache_path: str = MASTERFILELIST_CACHE, force_refresh: bool = False, verbose: bool = False) -> List[str]:
    #Download and cache the GDELT masterfilelist with every published file
    if os.path.exists(cache_path) and not force_refresh:
        if verbose:
            print(f"Loaded MASTERFILELIST from cache ({cache_path}).")
        with open(cache_path, "r", encoding="utf-8") as fh:
            raw_lines = [l.rstrip("\n") for l in fh if l.strip()]
    else:
        if verbose:
            print("Downloading MASTERFILELIST from GDELT...")
        try:
            r = requests.get(MASTERFILELIST_URL, timeout=60)
            r.raise_for_status()
            text = r.text
            with open(cache_path, "w", encoding="utf-8") as fh:
                fh.write(text)
            raw_lines = [l for l in text.splitlines() if l.strip()]
            if verbose:
                print(f"Downloaded MASTERFILELIST ({len(raw_lines)} total lines).")
        except Exception as e:
            print("Could not download MASTERFILELIST:", e)
            return []    
    gkg_paths = []
    for ln in raw_lines:
        p = extract_gkg_path_from_line(ln)
        if p:
            if p.lower().startswith("http"):
                try:
                    parsed = urlparse(p)
                    rel = parsed.path.lstrip("/")
                    gkg_paths.append(rel)
                except Exception:
                    gkg_paths.append(p)
            else:
                gkg_paths.append(p)
    if verbose:
        print(f"Extracted {len(gkg_paths)} GKG path tokens from masterfilelist.")
#      A list of cleaned GKG path tokens (relative paths or URL paths).
#      Returns [] on download/parsing error.
    return gkg_paths

#Given a target year, return a sampled list of full GDELT GKG file URLs for that year using the MASTERFILELIST.
def gdelt_gkg_urls_for_year_from_master(year: int, files_per_year_sample: int = FILES_PER_YEAR_SAMPLE_DEFAULT, force_refresh_master: bool = False, verbose: bool = False) -> List[str]:
        #This function:
    #1. loads the masterfilelist (cached or downloaded),
    #2. filters only GKG files belonging to the specified year,
    #3. samples a fixed number of files evenly across the year,
    #4. returns full HTTP URLs ready for downloading
    #     
    all_paths = download_masterfilelist(force_refresh=force_refresh_master, verbose=verbose)
    # If the masterfilelist could not be loaded, abort early
    if not all_paths:
        if verbose:
            print("MASTERFILELIST unavailable or empty.")
        return []
    # Convert year to string so we can match it inside filenames (YYYY)
    year_token = str(year)
    # Filter for GKG files that:
    # - contain the year token
    # - end with .gkg.csv.zip
    gkg_paths = [p for p in all_paths if year_token in p and p.lower().endswith(".gkg.csv.zip")]
# If no files exist for that year, stop early
    if not gkg_paths:
        if verbose:
            print(f"No GKG files found for year {year}.")
        return []
    #sort chronologically
    gkg_paths_sorted = sorted(gkg_paths)
    #total number of files for year
    total = len(gkg_paths_sorted)
    step = max(1, math.floor(total / max(1, files_per_year_sample)))
    # Compute a step size so we sample evenly across the year
    sampled = [gkg_paths_sorted[i] for i in range(0, total, step)]
    if len(sampled) > files_per_year_sample:
        sampled = sampled[:files_per_year_sample]
    full_urls = [urljoin(GDELT_BASE, s) if not s.lower().startswith("http") else s for s in sampled]
    if verbose:
        print(f"Year {year}: found {total} available GKG files; sampling {len(full_urls)} files.")
    return full_urls

# ---------------- title scoring & selection (improved) ----------------
# Common English and financial “glue words” that appear in real article titles
# Helps with title recognition, as GDELT doesn't automatically store the title
_TITLE_STOPWORDS = set([
    "the", "and", "of", "in", "for", "to", "with", "on", "by", "from", "at",
    "company", "companies", "reports", "says", "announces", "buys", "sells", "acquires",
    "beats", "misses", "expects", "raises", "lowers", "files", "appoints", "stock",
    "shares", "investors", "market", "trading", "up", "down", "after", "quarterly"
])
# Regex that matches GKG-style machine tokens such as:
#   wc:984,c12.3:9,c1.2:4
# These should not be used as titles
_TOKEN_LIKE_RE = re.compile(r'^(?:[a-z0-9]{1,4}[:.]\d+(?:[, ]?)?)+$', flags=re.IGNORECASE)
_URL_SLUG_CLEAN_RE = re.compile(r'[-_]+')

def score_title_candidate(s: str) -> float:
    #Assign a numeric score representing how likely a string is to be a real article title
    if not s:
        return float("-inf")
    
    s = s.strip()
    
    # Reject pure machine-token strings
    if _TOKEN_LIKE_RE.match(s):
        return float("-inf")
    
    # Reject strings with excessive punctuation (likely metadata or entity lists)
    if s.count(":") > 3 or s.count(",") > 6:
        return float("-inf")
    
    if (s.count(";") >= 2 and s.count(",") > 2) or (s.count(";") > 3):
        return float("-inf")
    
    # Text statistics
    length = len(s)
    words = s.split()
    word_count = len(words)
    letters = sum(1 for ch in s if ch.isalpha())
    digits = sum(1 for ch in s if ch.isdigit())
    punct = sum(1 for ch in s if ch in ".,:;!?()-—–'\"")
    cap_words = sum(1 for w in words if w and w[0].isupper())
    # Reject strings that are too short, too long, or mostly non-letters    # Reject strings that are too short, too long, or mostly non-letters
    if letters < 5 or length < 10 or length > 300:
        return float("-inf")
    
    if word_count < 3:
        return float("-inf")
    
    score = 0.0
    
    # Length bonuses
    score += min(25, length / 3.0)
    score += min(20, word_count * 2.5)
    
    # Punctuation (moderate amounts are good)
    score += min(10, punct * 1.5)
    
    # Capitalization (titles have proper caps)
    score += cap_words * 1.5
    
    # Penalize too many digits
    if digits / max(1, length) > 0.20:
        score -= 30
    
    # Reward common title words
    lower = s.lower()
    stopword_hits = sum(1 for w in _TITLE_STOPWORDS if f" {w} " in f" {lower} ")
    score += stopword_hits * 3.0
    
    # Bonus for typical title structure markers
    if ":" in s or "—" in s or " - " in s:
        score += 8.0
    
    # Penalize if too many non-letter characters
    nonletters = length - letters
    if nonletters / max(1, length) > 0.4:
        score -= 25
    
    # Penalize machine-like tokens
    token_like_count = len(re.findall(r'\b[a-z]\d{1,3}\b', lower))
    score -= token_like_count * 3.0
    
    # Bonus for financial keywords in title
    financial_words = ["stock", "market", "shares", "profit", "revenue", "earnings", 
                      "investors", "trading", "nasdaq", "dow", "s&p"]
    financial_hits = sum(1 for w in financial_words if w in lower)
    score += financial_hits * 5.0
    
    return score


def get_title_from_row(row_list: List[str], prefer_index: Optional[int] = None) -> Optional[str]:
    #Extract the best title candidate from a GDELT GKG row
    candidates = []
    
    # GDELT GKG V2 format: Column 16 often contains PAGE_TITLE !!
    # Check columns 15-17 first (0-indexed)
    priority_indices = [16, 15, 17]
    for idx in priority_indices:
        if len(row_list) > idx:
            v = (row_list[idx] or "").strip()
            if v and "PAGE_TITLE" not in v.upper():
                candidates.append((f"priority_{idx}", v, 2.0))  # Higher weight
    
    # Check common title positions (columns 8-25)
    start, end = 8, min(len(row_list), 26)
    for idx in range(start, end):
        v = (row_list[idx] or "").strip()
        if v and "PAGE_TITLE" not in v.upper():
            candidates.append((f"col{idx}", v, 1.0))
    
    # Deduplicate
    seen = set()
    uniq = []
    for tag, text, weight in candidates:
        if text in seen or len(text) < 10:
            continue
        seen.add(text)
        uniq.append((tag, text, weight))
    
    #score all candidates
    scored = []
    for tag, text, weight in uniq:
        sc = score_title_candidate(text) * weight
        scored.append((sc, tag, text))
    
    # Try to extract from URL as fallback
    url_text = None
    for p in row_list:
        if p and ("http://" in p.lower() or "https://" in p.lower()):
            url_text = p.strip()
            break
    
    if url_text:
        path = urlparse(url_text).path or ""
        slug = path.rstrip("/").split("/")[-1] if path else ""
        slug = _URL_SLUG_CLEAN_RE.sub(" ", slug)
        slug = re.sub(r'\.html?$', '', slug, flags=re.IGNORECASE)
        slug = re.sub(r'%20', ' ', slug)
        slug = re.sub(r'\d{8,}', '', slug)  # Remove long digit sequences
        slug = slug.strip()
        if slug and len(slug) > 10:
            scored.append((score_title_candidate(slug) * 0.7, "slug", slug))
    
    if not scored:
        return None
    
    # Sort by score and pick best
    scored.sort(reverse=True, key=lambda x: x[0])
    best_score, best_tag, best_text = scored[0]
    
    # Only accept if score is reasonable
    if best_score < 15:
        return None
    
    return best_text


# ---------------- fast streaming parser ----------------
def get_description_from_row(row_list: List[str]) -> str:
    #Extract description/themes from GDELT GKG row
    # Column 7 contains V2THEMES
    if len(row_list) > 7:
        themes = (row_list[7] or "").strip()
        if themes:
            # Clean up theme tags
            themes = themes.replace(";", ", ")
            themes = re.sub(r'[A-Z_]{3,}', lambda m: m.group(0).title().replace("_", " "), themes)
            if len(themes) > 200:
                themes = themes[:200] + "..."
            return themes
    return ""

# ---------------- fast streaming parser ----------------
def process_gkg_stream(url: str, keywords: List[str], source_domains: List[str], verbose: bool = False, session: Optional[requests.Session] = None) -> List[Dict]:
    #Process a single GDELT GKG file (URL) and return a list of article dicts that
    #match the provided keywords/domains.

    #    Returns list of dicts with keys:
    #  - published_at (ISO timestamptz)
     # - title
    #  - description
    #  - url
    #  - inserted_at (UTC timestamp)

    sess = session or requests.Session()
    cache_name = os.path.join(GDELT_CACHE_DIR, url.replace("http://", "").replace("https://", "").replace("/", "_"))
    #if the file was already cached read it from disk
    if os.path.exists(cache_name):
        with open(cache_name, "rb") as fh:
            content = fh.read()
    else:   # Otherwise, download the file and save a local copy (best-effort write).
        r = sess.get(url, timeout=60)
        r.raise_for_status()
        content = r.content
        try:
            with open(cache_name, "wb") as fh:
                fh.write(content)
        except Exception:
            pass
    #detect file format
    # GDELT file blobs can be gzipped streams, zip archives, or plain text.
    iterator = None
    # Check gzip magic bytes: 0x1f 0x8b
    if len(content) >= 2 and content[:2] == b'\x1f\x8b':
        iterator = gzip.open(io.BytesIO(content), "rt", encoding="utf-8", errors="ignore")
    # Check ZIP file magic bytes: "PK\x03\x04"
    elif len(content) >= 4 and content[:4] == b'PK\x03\x04':
        z = zipfile.ZipFile(io.BytesIO(content))
        inner = None
        for name in z.namelist():
            ln = name.lower()
            if ln.endswith(".csv") or ln.endswith(".gkg") or ln.endswith(".gkg.csv"):
                inner = name
                break
        if inner is None:
            inner = z.namelist()[0]
        raw = z.open(inner)
        iterator = io.TextIOWrapper(raw, encoding="utf-8", errors="ignore")
    # Treat as plain text if not gzip/zip: decode and use a StringIO iterator.
    else:
        iterator = io.StringIO(content.decode("utf-8", errors="ignore"))

    #iterate lines
    results = []
    for line in iterator:
        parts = line.rstrip("\n").split("\t")
        
        # Extract URL
        url_cell = None
        if len(parts) > 4:
            url_cell = (parts[4] or "").strip()
        
        if not url_cell or not ("http://" in url_cell.lower() or "https://" in url_cell.lower()):
            continue
        
        # Domain filter
        # domain_match returns True if source_domains is empty (ie., no restriction)
        # otherwise it checks whether one of the configured domain substrings appears in the host.

        if not domain_match(url_cell, source_domains):
            continue
        
        # Extract title
        title_candidate = get_title_from_row(parts)
        if not title_candidate:
            continue
        
        # Extract description
        # Some GKG implementations store a summary field, use helper to extract it.
        description = get_description_from_row(parts)
        
        # Keyword matching on title + description + URL
        combined_text = f"{title_candidate} {description} {url_cell}".lower()
        if not keyword_match(combined_text, keywords):
            continue
        
        # Extract and parse publish date (column 1 in GKG V2)
        published_raw = parts[1] if len(parts) > 1 else ""
        try:
            published_dt = datetime.strptime(published_raw.strip(), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            published_iso = published_dt.isoformat()
        except Exception:
            continue
        #appead normalized records to results
        results.append({
            "published_at": published_iso,
            "title": title_candidate,
            "description": description,
            "url": url_cell,
            "inserted_at": now_utc_iso(),
        })
    
    try:
        iterator.close()
    except Exception:
        pass
    
    return results


def collect_for_year_concurrent(year: int, files_per_year_sample: int, keywords: List[str], source_domains: List[str], max_workers: int = 3, verbose: bool = False, articles_per_year: int = ARTICLES_PER_YEAR_DEFAULT) -> List[Dict]:
    
    #Collect articles for a given year using concurrent processing
    #    This function:
    #   1.Retrieves a sampled list of GDELT GKG file URLs for the given year
    #   2. Processes those files in parallel using a thread pool
    #  3. Aggregates all extracted article records
    #  4. Deduplicates results by URL
    #  5. Sorts by publication date and returns up to articles_per_year items


    # Retrieve a list of GKG file URLs sampled evenly across the given year
    urls = gdelt_gkg_urls_for_year_from_master(year, files_per_year_sample, verbose=verbose)
    # If no files were found (or masterfilelist failed), return empty result
    if not urls:
        return []
    
    # Create a single requests.Session to reuse TCP connections
    # across concurrent downloads (significantly improves performance)
    sess = requests.Session()
    results = []
    
    # Create a thread pool for concurrent file processing
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(process_gkg_stream, u, keywords, source_domains, verbose, sess): u for u in urls}
            # Iterate over completed futures as they finish (not submission order)
        for fut in tqdm(as_completed(futures), total=len(futures), desc=f"parsing {year}", unit="file"):
            u = futures[fut]
            try:
                res = fut.result()
                if res:
                    results.extend(res)
                if verbose: #if CLI option
                    print(f"  parsed {u}: {len(res)} matches")
            except Exception as e:
                if verbose: #if CLI option
                    print(f"  skipped {u} due to {e}")
    
    # Deduplicate by URL
    #remove duplicate articles that  may appear across multiple GKG files
    dedup = {}
    for a in results:
        dedup.setdefault(a["url"], a)
    dedup_list = list(dedup.values())
    
    # Sort by date and limit
    dedup_sorted = sorted(dedup_list, key=lambda x: x.get("published_at") or "")
    return dedup_sorted[:articles_per_year]

# ---------------- CSV writer ----------------
def write_csv(rows: List[Dict], csv_path: str):

    
    #Write results to CSV file
    fieldnames = [
        "published_at",
        "title",
        "description",
        "url",
        "inserted_at",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (r.get(k) or "") for k in fieldnames})


# ---------------- CLI / main ----------------
def parse_args():
    #argument options for CLI
    p = argparse.ArgumentParser(description="Ingest historical news from GDELT GKG and output CSV")
    p.add_argument("--output", "-o", default=DEFAULT_OUTPUT, help="Output CSV path")
    p.add_argument("--years", "-y", nargs="+", type=int, default=YEARS_DEFAULT, help="Years to collect")
    p.add_argument("--articles-per-year", "-n", type=int, default=ARTICLES_PER_YEAR_DEFAULT, help="Target articles per year")
    p.add_argument("--files-per-year", "-f", type=int, default=FILES_PER_YEAR_SAMPLE_DEFAULT, help="Number of GKG files to sample per year")
    p.add_argument("--max-workers", type=int, default=3, help="Concurrent file fetch/parse workers")
    p.add_argument("--keywords", "-k", nargs="+", default=KEYWORDS_DEFAULT, help="Keywords to match")
    p.add_argument("--domains", "-d", nargs="*", default=SOURCE_DOMAINS_DEFAULT, help="Optional domain substrings to restrict to")
    p.add_argument("--force-refresh-master", action="store_true", help="Force refresh of MASTERFILELIST cache")
    p.add_argument("--verbose", action="store_true", help="Verbose output")
    return p.parse_args()

def main():
    args = parse_args()
    output = args.output
    years: List[int] = sorted(args.years)
    articles_per_year = args.articles_per_year
    files_per_year = args.files_per_year
    keywords = args.keywords
    domains = args.domains
    force_refresh = args.force_refresh_master
    verbose = args.verbose
    max_workers = args.max_workers

    if verbose:
        print("Configuration:")
        print("  output:", output)
        print("  years:", years)
        print("  articles_per_year:", articles_per_year)
        print("  files_per_year:", files_per_year)
        print("  keywords:", len(keywords), "keywords")
        print("  domains:", len(domains) if domains else "(all)")
        print("  max_workers:", max_workers)
        print("  force_refresh_master:", force_refresh)

    all_rows: List[Dict] = []
    for year in years:
        rows = collect_for_year_concurrent(
            year=year,
            files_per_year_sample=files_per_year,
            keywords=keywords,
            source_domains=domains,
            max_workers=max_workers,
            verbose=verbose,
            articles_per_year=articles_per_year,
        )
        print(f"{year}: {len(rows)} articles")
        all_rows.extend(rows)

    write_csv(all_rows, output)
    print(f"Wrote {len(all_rows)} rows to {output}")

if __name__ == "__main__":
    #for cli
    main()