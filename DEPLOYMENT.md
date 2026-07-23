# Deployment & Team Sharing Guide

Two separate things, do both:

- **GitHub** → your team can see, edit, and run the code
- **Live URLs (Render + Vercel)** → pilot testers can use the app with zero setup, just a link

Both are free for this scale of use.

---

## Part A — Share the code with your team via GitHub

1. Create a GitHub account if you don't have one, then create a new repo
   (e.g. `bedalert`) at github.com/new. Keep it **private** for now, add your
   teammates under Settings → Collaborators.

2. In VS Code, open a terminal at the project root (`bedalert-app/`):
   ```bash
   git init
   git add .
   git commit -m "BedAlert v0.2 — pilot-ready web app + USSD"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/bedalert.git
   git push -u origin main
   ```

3. Your teammates run:
   ```bash
   git clone https://github.com/YOUR-USERNAME/bedalert.git
   ```
   then follow the existing README to run backend + frontend locally.

4. Add a `.gitignore` first so you don't commit dependency folders (see below).

---

## Part B — Deploy live so pilot testers don't need VS Code

### Backend → Render

1. Go to render.com, sign up (free), connect your GitHub repo.
2. New → Web Service → select your `bedalert` repo.
3. Render should detect `render.yaml` automatically. If not, set manually:
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Deploy. You'll get a URL like `https://bedalert-backend.onrender.com`.
5. Test it: visit `https://bedalert-backend.onrender.com/docs` — you should
   see the FastAPI docs page.

Note: Render's free tier sleeps after inactivity and takes ~30–60 seconds to
wake up on the first request. Warn your pilot testers, or open the URL
yourself 2 minutes before a session starts.

### Frontend → Vercel

1. Go to vercel.com, sign up (free), import your GitHub repo.
2. Set root directory to `frontend`.
3. Add an environment variable:
   - `VITE_API_URL` = `https://bedalert-backend.onrender.com` (your Render URL from above, no trailing slash)
4. Deploy. You'll get a URL like `https://bedalert.vercel.app`.

That URL is what you send to pilot testers and what you present on Demo Day —
no localhost, no setup, works on their phone browser too.

### Redeploying after changes

Both Render and Vercel auto-redeploy when you `git push` to `main`. So the
workflow becomes: edit code in VS Code → commit → push → both services update
automatically within a minute or two.

---

## .gitignore (add this before your first commit)

```
node_modules/
dist/
venv/
__pycache__/
*.pyc
.env
```
