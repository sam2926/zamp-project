# <span style="color:#D6336C">Deploy — Google Cloud Run (Docker)</span>

One container serves the API and the built frontend at a single public URL. No API key is
baked in: visitors paste their own (`X-LLM-Key`), so the service costs nothing to run beyond
build/idle. It scales to zero when idle. First build takes ~10–15 minutes (PyTorch + the OCR
model are installed and baked into the image); after that Cloud Build caches layers.

**Live URL:** <https://invoice-extraction-nnmkwkhoma-uc.a.run.app>

## <span style="color:#2E7D32">What's deployed</span>

- **GCP project:** `zamp-project-505407`  ·  **service:** `invoice-extraction`  ·  **region:** `us-central1`
- **Runtime config:** `--memory 4Gi --cpu 2 --min-instances 0 --max-instances 2 --timeout 600 --allow-unauthenticated`
- The URL above never changes across redeploys, so it stays the link you share.

## <span style="color:#2E7D32">Prerequisites (one-time)</span>

**<span style="color:#B8860B">1 · The `gcloud` CLI, authenticated.</span>** Installed here via Homebrew at `/opt/homebrew/bin/gcloud`. Sign in once with `gcloud auth login` and make sure the active account has deploy rights on `zamp-project-505407`. After that, redeploys are non-interactive.

**<span style="color:#B8860B">2 · Nothing else.</span>** The build is entirely from the repo's `Dockerfile` — no separate registry push, no secrets to set.

## <span style="color:#2E7D32">Redeploy (after any change)</span>

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd /Users/sam/Desktop/zamp-project
gcloud run deploy invoice-extraction --source . --region us-central1 \
  --allow-unauthenticated --memory 4Gi --cpu 2 --min-instances 0 --max-instances 2 \
  --timeout 600 --project zamp-project-505407 --quiet
```

Builds from the local `Dockerfile` via Cloud Build (~10–15 min). `--source .` uploads the
working tree (minus everything in `.gitignore`), so commit or at least save your changes
first. **Verify after it finishes:**

```bash
curl -s https://invoice-extraction-nnmkwkhoma-uc.a.run.app/api/health
# → {"status":"ok",...}   (HTTP 200)
```

> **Watch the log, not the exit code.** If you pipe the deploy command (e.g. `| tail`), the
> reported exit status is the pipe's, not gcloud's. Read the output for `Service URL` (success)
> or `Build failed` (failure) rather than trusting a `0`.

## <span style="color:#2E7D32">Things worth knowing</span>

**<span style="color:#B8860B">1 · No secrets, by design.</span>** Uploads use the visitor's own key via the `X-LLM-Key` header; a keyless upload is refused with `400`. Do **not** set an `OPENAI_API_KEY` on the service — that would let anyone spend your key.

**<span style="color:#B8860B">2 · The port is injected.</span>** Cloud Run sets `PORT`; the Dockerfile listens on `${PORT:-7860}`, so local and Cloud Run both work with no change.

**<span style="color:#B8860B">3 · First upload is slow, then warm.</span>** The OCR model is baked into the image, so there is no download — but the first inference on a cold CPU still takes a few seconds. The service scales to zero when idle; the next visit wakes it (the model is already in the image, so wake-up is quick).

**<span style="color:#B8860B">4 · Storage is ephemeral.</span>** The dedup cache and learned corrections live in the container's SQLite file and reset on every rebuild/restart — fine for a demo. Persisting them across restarts needs a mounted volume or an external store.

**<span style="color:#B8860B">5 · Known-vendor matching is quiet here.</span>** The layout index is seeded from `data/ocr_cache`, which is gated DocILE data and not shipped — so uploads read as "new layout." Extraction, confidence, review and learning all work regardless.

## <span style="color:#2E7D32">Dockerfile notes</span>

**<span style="color:#B8860B">1 · Multi-stage build.</span>** `python:3.9-slim` base; a Node 20 stage builds the React frontend, which FastAPI then serves as static files from the same origin.

**<span style="color:#B8860B">2 · CPU-only PyTorch.</span>** Installed with **both** `--index-url .../cpu` **and** `--extra-index-url https://pypi.org/simple`. Without the extra index, build dependencies (e.g. `flit_core`) go missing and the build fails — this was a real bug, keep both.

**<span style="color:#B8860B">3 · Runs unprivileged.</span>** As uid 1000, listening on `${PORT:-7860}`.

## <span style="color:#2E7D32">Note — this replaced a Hugging Face Spaces plan</span>

Deployment was originally planned for a Hugging Face Docker Space, but mid-build HF made free
Docker Spaces require a paid subscription (`402 Payment Required`), so we moved to Cloud Run.
There is **no** HF Space and none should be created — it would be a redundant, paid second
deployment. Cloud Run is the single source of truth for what's live.
