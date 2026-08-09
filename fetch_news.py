#!/usr/bin/env python3
"""
Daily energy & shipping market dashboard — data pipeline.

Pulls RSS feeds from:
  - EIA Today in Energy
  - Oilprice
  - Splash247 (shipping)
  - Ship & Bunker (bunker prices / marine fuels)
  - FT Alphaville
  - FRED Blog (macro / energy data commentary)

Synthesises a single "daily headline take" via the DeepSeek API,
written with British spelling conventions, aimed at a commodities
derivatives trader.

Usage:
    export DEEPSEEK_API_KEY="sk-..."
    python3 fetch_news.py

Output:
    data/latest.json   (consumed by index.html)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import feedparser
import requests

# ---------------------------------------------------------------- config ---

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "latest.json")

FEEDS = {
    "EIA Today in Energy": "https://www.eia.gov/rss/todayinenergy.xml",
    "Oilprice":            "https://oilprice.com/rss/main",
    "Splash247":           "https://splash247.com/feed/",
    "Ship & Bunker":       "https://shipandbunker.com/rss",
    "FT Alphaville":       "https://ftalphaville.ft.com/feed/",
    "FRED Blog":           "https://fredblog.stlouisfed.org/feed/",
}

ITEMS_PER_FEED = 8
HTTP_TIMEOUT = 30

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
}

# ------------------------------------------------------------- fetching ---

def fetch_feed(name: str, url: str) -> dict:
    """Fetch one RSS/Atom feed; return normalised item list."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        items = []
        for e in parsed.entries[:ITEMS_PER_FEED]:
            summary = getattr(e, "summary", "") or ""
            # strip tags crudely
            import re
            summary = re.sub(r"<[^>]+>", " ", summary)
            summary = re.sub(r"\s+", " ", summary).strip()[:400]
            items.append({
                "title": (getattr(e, "title", "") or "").strip(),
                "link": getattr(e, "link", "") or "",
                "published": getattr(e, "published",
                                     getattr(e, "updated", "")) or "",
                "summary": summary,
            })
        return {"source": name, "url": url, "ok": True,
                "count": len(items), "items": items}
    except Exception as exc:  # noqa: BLE001
        return {"source": name, "url": url, "ok": False,
                "count": 0, "items": [], "error": str(exc)}


# ----------------------------------------------------------- synthesis ---

def build_prompt(feeds: list) -> str:
    lines = []
    for f in feeds:
        if not f["ok"]:
            continue
        lines.append(f"### {f['source']}")
        for it in f["items"]:
            lines.append(f"- {it['title']} ({it['published']})")
            if it["summary"]:
                lines.append(f"  {it['summary'][:200]}")
    headlines = "\n".join(lines)
    return f"""You are a senior commodities derivatives strategist writing for a \
trader covering oil, refined products and dry bulk freight.

Below are today's headlines from EIA Today in Energy, Oilprice, Splash247, \
Ship & Bunker, FT Alphaville and the FRED Blog.

Write a DAILY HEADLINE TAKE of exactly five sentences:
1. The single most market-relevant story and why it matters for crude/products.
2. The second theme (shipping/freight/macro) and its transmission into \
energy or freight markets.
3. What the flow/positioning/inventory angle is, if any.
4. One cross-market link (e.g. gasoil vs bunker, tonne-miles, rates vs FX).
5. What to watch in the next 24 hours.

Rules:
- British spelling conventions throughout (e.g. normalise, tonnes, \
programme, centre, whilst).
- Trader tone: direct, no fluff, no bullet points, no headings.
- Reference specific numbers from the headlines where available.
- Do not invent facts not present in the headlines.

HEADLINES:
{headlines}"""


def synthesise(feeds: list) -> str:
    """Call DeepSeek; fall back to a mechanical summary on failure."""
    try:
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system",
                 "content": "You write concise market commentary in British "
                            "English for professional commodity traders."},
                {"role": "user", "content": build_prompt(feeds)},
            ],
            "temperature": 0.4,
            "max_tokens": 600,
        }
        r = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001
        top = []
        for f in feeds:
            if f["ok"] and f["items"]:
                top.append(f"{f['source']}: {f['items'][0]['title']}")
        return ("DeepSeek synthesis unavailable (%s). Top headlines — %s"
                % (exc, " | ".join(top)))


# ---------------------------------------------------------------- main ---

def main() -> int:
    feeds = [fetch_feed(n, u) for n, u in FEEDS.items()]
    ok = sum(1 for f in feeds if f["ok"])
    print(f"feeds ok: {ok}/{len(feeds)}")
    for f in feeds:
        print(f"  {f['source']:<20} {f['count']:>2} items"
              + ("" if f["ok"] else f"  ERROR: {f['error'][:80]}"))

    print("synthesising daily take via DeepSeek…")
    take = synthesise(feeds)

    out = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "take": take,
        "feeds": feeds,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    # inline fallback so the dashboard also works over file://
    fb_path = os.path.join(os.path.dirname(OUT_PATH), "fallback.js")
    with open(fb_path, "w", encoding="utf-8") as fh:
        fh.write("window.__FALLBACK__ = "
                 + json.dumps(out, ensure_ascii=False) + ";")
    print(f"wrote {OUT_PATH} and {fb_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
