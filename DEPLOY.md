# Deploying RADAR (free hosting)

This puts the app **live on the internet** — the version you link from your
resume and LinkedIn. Backend goes on Render, frontend on Vercel. Both have free
tiers and connect to your GitHub repo.

## 0. Push to GitHub

```bash
git init
git add .
git commit -m "RADAR: full-stack resume analyzer"
git branch -M main
git remote add origin https://github.com/<you>/radar.git
git push -u origin main
```

## 1. Backend → Render

1. Go to https://render.com and sign in with GitHub.
2. **New → Blueprint**, pick your repo. Render reads `render.yaml` automatically.
3. When prompted, set the secret **`GEMINI_API_KEY`** (or leave it blank to use
   the offline rewriter).
4. Deploy. You get a URL like `https://radar-api.onrender.com`.
5. Confirm it works: open `https://radar-api.onrender.com/docs`.

> Note: Render's free tier sleeps after inactivity; the first request after idle
> takes ~30s to wake. That's normal and fine for a demo.

## 2. Frontend → Vercel

1. Go to https://vercel.com and import the same repo.
2. Set **Root Directory** to `frontend`. Vercel auto-detects Vite.
3. Add an environment variable:
   - `VITE_API_URL = https://radar-api.onrender.com`  (your Render URL, no trailing slash)
4. Deploy. You get a URL like `https://radar.vercel.app`.

## 3. Point the frontend at the backend

The frontend reads `VITE_API_URL` at build time (see `frontend/src/api.js`). With
the variable set in step 2, all `/api` calls go to your Render backend. Redeploy
the frontend if you change it.

## 4. Put the live link everywhere

- Add it to the top of this README (`Live demo:`).
- Add it to your GitHub repo's "About" website field.
- Add it to your resume and LinkedIn featured section.

## Alternative: single-box Docker deploy

Any VPS (or a service that runs Docker Compose) can host the whole stack:

```bash
GEMINI_API_KEY=your_key docker compose up --build -d
# app on port 8080, nginx proxies /api to the backend container
```
