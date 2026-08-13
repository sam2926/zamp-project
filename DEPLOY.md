# <span style="color:#D6336C">Deploy — Hugging Face Space (Docker)</span>

One container serves the API and the built frontend at a single public URL. No API key is
baked in: visitors paste their own, so the Space costs you nothing to run. First build takes
~10–15 minutes (PyTorch + the OCR model are installed and baked in); after that it's cached.

## <span style="color:#2E7D32">One-time setup</span>

**<span style="color:#B8860B">1 · Create the Space.</span>** On [huggingface.co/new-space](https://huggingface.co/new-space): pick **Docker** (blank template), **CPU basic** (free), visibility **Public**. Name it, e.g. `invoice-extraction`.

**<span style="color:#B8860B">2 · Push this repo to it.</span>** The Space is its own git remote; add it and push. Use a Hugging Face **access token** (Settings → Access Tokens, `write` scope) as the git password.

```bash
git remote add space https://huggingface.co/spaces/<your-username>/invoice-extraction
git push space main
```

**<span style="color:#B8860B">3 · Watch it build.</span>** The Space builds the `Dockerfile` automatically. When the status turns **Running**, the app is live at:

```
https://<your-username>-invoice-extraction.hf.space
```

That's the URL to share. The frontend and the `/api/*` endpoints are the same origin.

## <span style="color:#2E7D32">Things worth knowing</span>

**<span style="color:#B8860B">1 · The port is 7860.</span>** Hugging Face routes to it by default; the Dockerfile already listens there. Nothing to configure.

**<span style="color:#B8860B">2 · No secrets to set.</span>** Uploads use the visitor's own key (`X-LLM-Key`); a keyless upload is refused with `400`. Do **not** add an `OPENAI_API_KEY` Space secret — that would let anyone spend your key.

**<span style="color:#B8860B">3 · First upload is slow, then warm.</span>** The OCR model is baked into the image, so there's no download — but the first inference on a cold CPU still takes a few seconds. Free Spaces sleep when idle; the next visit wakes the container (the model is already in the image, so wake-up is quick).

**<span style="color:#B8860B">4 · Storage is ephemeral.</span>** The dedup cache and learned corrections live in the container's SQLite file and reset on rebuild/restart — fine for a demo. Persisting them needs Hugging Face's paid persistent storage.

**<span style="color:#B8860B">5 · Known-vendor matching is quiet here.</span>** The layout index is seeded from `data/ocr_cache`, which is gated DocILE data and not shipped — so uploads read as "new layout." The extraction, confidence, review and learning all work regardless.

## <span style="color:#2E7D32">Optional: a nicer Space card</span>

To set the Space's title and icon, add this front-matter to the **top of the README on the
Space** (keep it off the GitHub copy). It is optional — the Docker build works without it.

```yaml
---
title: Invoice Extraction
emoji: 🧾
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---
```
