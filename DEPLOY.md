# Deploying RADAR (free hosting)

This puts the app **live on the internet** — the version you link from your
resume and LinkedIn. Database on Neon, backend on Render, frontend on Vercel.
All three have free tiers and connect to your GitHub repo.

Do them in this order. The backend needs a database URL before it starts, or
accounts will not survive its first restart.

## 0. Push to GitHub

```bash
git push origin main
```

## 1. Database → Neon

RADAR needs a database that outlives the container. Render's free tier gives a
web service an **ephemeral filesystem**: everything written to disk is wiped on
every deploy, restart, and cold start. A SQLite file there would lose every
account overnight. Neon's free Postgres does not have that problem, and unlike
some alternatives it does not pause a project after a week of inactivity — which
matters if the next person to open your link is an interviewer.

1. Go to https://neon.com and sign up (GitHub login is quickest).
2. Create a project. Pick the region closest to you.
3. **Decline "Neon Auth"** — RADAR has its own authentication, and a second
   system would just add unused tables.
4. Copy the **connection string**. It looks like
   `postgresql://user:password@host/dbname?sslmode=require`.

Treat that string as a password. It goes into Render's dashboard and nowhere
else — not into a file, not into git.

## 2. Backend → Render

1. Go to https://render.com and sign in with GitHub.
2. **New → Blueprint**, pick your repo. Render reads `render.yaml` automatically.
3. Set these environment variables:

   | Variable | Value |
   |----------|-------|
   | `DATABASE_URL` | the Neon connection string from step 1 |
   | `JWT_SECRET` | use Render's **Generate** button, or `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `RADAR_ENV` | `production` |
   | `ALLOWED_ORIGINS` | your Vercel URL — fill this in after step 3 |
   | `GEMINI_API_KEY` | optional; blank uses the offline engine |

4. Deploy. You get a URL like `https://radar-api-abxi.onrender.com`.
5. Confirm it worked: open `/api/health`. It reports which storage backend is
   live — **`"storage": "postgres"`** means the database is wired up. If it says
   `sqlite`, `DATABASE_URL` did not reach the app and your data will not survive.

`RADAR_ENV=production` makes a missing `JWT_SECRET` a startup error rather than
a silent fall back to the insecure development key.

> Render's free tier sleeps after 15 minutes idle, so the first request after a
> quiet spell takes ~50 seconds. The included GitHub Actions workflow
> (`.github/workflows/keep-warm.yml`) pings it each weekday morning so the first
> visit of the day is not a cold start. Set a repository **variable** called
> `RADAR_API_URL` to your Render URL to enable it.

## 3. Frontend → Vercel

1. Go to https://vercel.com and import the same repo.
2. Set **Root Directory** to `frontend`. Vercel auto-detects Vite.
3. Add an environment variable:
   - `VITE_API_URL = https://radar-api-abxi.onrender.com` (your Render URL, no
     trailing slash)
4. Deploy. You get a URL like `https://radar-six-iota.vercel.app`.
5. Go back to Render and set **`ALLOWED_ORIGINS`** to that Vercel URL, then let
   it redeploy. Until you do, the API accepts requests from any origin.

`VITE_API_URL` is read at build time (see `frontend/src/api.js`), so changing it
needs a redeploy, not just a refresh.

## 4. Check it end to end

1. Open the Vercel URL. The first load may take ~50 seconds while Render wakes.
2. Create an account.
3. In the Neon dashboard, open **Tables**. You should see `users`, `profiles`,
   `analyses` and `applications`, created automatically on startup, with your
   row in `users`. (An older deploy may also show a `preferences` table from the
   job feed that has since been removed; it is unused and safe to drop.)
4. Look at `password_hash` — a bcrypt digest beginning `$2b$`, not your password.

Step 3 is the one that matters. If `DATABASE_URL` were wrong, the app would fall
back to a local file and *appear* to work right up until the next restart wiped
it.

## 5. Put the live link everywhere

- The `Live demo:` line at the top of the README.
- Your GitHub repo's "About" website field.
- Your resume and LinkedIn featured section.

## Alternative: single-box Docker deploy

Any VPS (or a service that runs Docker Compose) can host the whole stack:

```bash
GEMINI_API_KEY=your_key JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))") docker compose up --build -d
# app on port 8080, nginx proxies /api to the backend container
```

Without `DATABASE_URL` this uses a SQLite file inside the container, which is
fine on a VPS with a persistent disk and not fine on ephemeral hosting.
