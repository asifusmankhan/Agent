# Asif Tech AI Agent — Deployment Guide
Frontend → Netlify (free) · Backend → Render (free)

---

## Step 1 — Get your Shopify Admin API token

1. Go to **Shopify Admin** → Settings → Apps → **Develop apps**
2. Click **Create an app** → name it "AI Agent"
3. Click **Configure Admin API scopes** and enable:
   - `read_products`
   - `read_orders`
   - `read_customers`
   - `read_analytics`
4. Click **Install app** → copy the **Admin API access token** (starts with `shpat_`)

---

## Step 2 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: Asif Tech AI Agent"
git remote add origin https://github.com/YOUR_USERNAME/asif-tech-agent.git
git push -u origin main
```

---

## Step 3 — Deploy backend on Render (free)

1. Go to **https://render.com** → New → **Web Service**
2. Connect your GitHub repo → select the **`backend/`** folder as root
3. Set:
   - **Runtime**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add **Environment Variables**:
   ```
   ANTHROPIC_API_KEY    = sk-ant-...
   SHOPIFY_STORE_URL    = asif208.myshopify.com
   SHOPIFY_ADMIN_TOKEN  = shpat_...
   ALLOWED_ORIGINS      = https://YOUR-SITE.netlify.app
   ```
5. Click **Deploy** — copy your Render URL, e.g. `https://asif-tech-ai-agent.onrender.com`

---

## Step 4 — Update netlify.toml

Open `netlify.toml` and replace `YOUR-APP.onrender.com` with your actual Render URL:

```toml
[[redirects]]
  from   = "/api/*"
  to     = "https://asif-tech-ai-agent.onrender.com/api/:splat"
  status = 200
  force  = true
```

Commit and push this change.

---

## Step 5 — Deploy frontend on Netlify

1. Go to **https://netlify.com** → Add new site → **Import from Git**
2. Connect your GitHub repo
3. Set **Publish directory** to `frontend`
4. Click **Deploy site**
5. Your agent is live at `https://YOUR-SITE.netlify.app`

---

## Testing locally

```bash
# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example .env   # fill in your values
uvicorn main:app --reload --port 8000

# Frontend — open frontend/index.html in a browser
# (it uses API_BASE="" which resolves to same origin)
# For local dev, change API_BASE in index.html to:
#   const API_BASE = "http://localhost:8000";
```

---

## Architecture

```
User browser (Netlify)
      │
      │  POST /api/chat
      ▼
Netlify CDN (proxy rewrite)
      │
      │  POST /api/chat
      ▼
FastAPI on Render
      │
      ├──► Claude API (Anthropic)
      │         └──► Agent tool loop
      │
      └──► Shopify Admin API
               ├── /products.json
               ├── /orders.json
               ├── /customers.json
               └── (analytics)
```
