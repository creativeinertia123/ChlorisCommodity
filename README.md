# Desk Brief 

A dashboard that pulls RSS feeds and synthesises them into a **daily headline take** via the DeepSeek API, written with British spelling conventions.

## Files

| Path | Purpose |
|---|---|
| `index.html` | The dashboard (no build step, plain HTML/JS) |
| `fetch_news.py` | Input script: fetches feeds, calls DeepSeek, writes data |
| `data/latest.json` | Latest fetched headlines + synthesised take |
| `data/fallback.js` | Same data inlined so the page works over `file://` |
| `.github/workflows/daily.yml` | GitHub Actions: daily refresh at 07:00 HKT |

## Run locally

```bash
pip install feedparser requests
export DEEPSEEK_API_KEY="sk-..."   # or edit the default in fetch_news.py
python3 fetch_news.py
python3 -m http.server 8000        # then open http://localhost:8000
```

## Deploy to GitHub Pages (github.io)

1. Create a repo named `<username>.github.io` (or any repo and use
   project pages).
2. Push this folder's contents to the `main` branch:
   ```bash
   git init && git add -A && git commit -m "desk brief"
   git remote add origin git@github.com:<username>/<repo>.git
   git push -u origin main
   ```
3. In the repo: **Settings → Secrets and variables → Actions → New
   repository secret**, name `DEEPSEEK_API_KEY`, value your DeepSeek key.
4. **Settings → Pages → Source: GitHub Actions** is not needed here —
   choose **Deploy from a branch**, branch `main`, folder `/ (root)`.
5. The Actions tab will run daily at 07:00 HKT (23:00 UTC), re-fetch the
   feeds, re-synthesise the take and commit the refreshed JSON. Use
   **Run workflow** for an immediate refresh.

Your dashboard will be live at `https://<username>.github.io/` (or
`https://<username>.github.io/<repo>/` for project pages).
