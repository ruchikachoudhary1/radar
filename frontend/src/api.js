// Thin API client for the RADAR backend.
// In dev, Vite proxies /api to the FastAPI server (see vite.config.js).
// In production, set VITE_API_URL to the deployed backend origin.
const BASE = import.meta.env.VITE_API_URL || "";

async function handle(res) {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function analyzeResume({ file, role, jobDescription }) {
  const form = new FormData();
  form.append("file", file);
  form.append("role", role || "");
  form.append("job_description", jobDescription || "");
  return handle(await fetch(`${BASE}/api/analyze`, { method: "POST", body: form }));
}

export async function rewriteBullet(bullet, variants = 3) {
  return handle(
    await fetch(`${BASE}/api/rewrite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bullet, variants }),
    })
  );
}

export async function getHistory() {
  return handle(await fetch(`${BASE}/api/history`));
}

export async function getHealth() {
  return handle(await fetch(`${BASE}/api/health`));
}
