# Stage 3 Setup Guide — SILMA-9B via vLLM on WSL2

This guide covers everything needed to get SILMA-9B running via vLLM inside WSL2, verify it from Windows, and run the Stage 3 smoke test.

---

## Prerequisites

### Hardware
- NVIDIA GPU with at least **16 GB VRAM** (SILMA-9B in bfloat16 needs ~18 GB; use `--gpu-memory-utilization 0.80` on a 16 GB card)
- Recommended: RTX 3090 / 4090, or any A-series card

### Software (Windows side)
- WSL2 enabled (Windows 10 build 19041+)
- NVIDIA driver ≥ 527.41 installed on Windows — this exposes the GPU to WSL2 automatically
- `uv` installed: `pip install uv` or via `winget install astral-sh.uv`

### Software (WSL2 side)
- Ubuntu 22.04 or 24.04 recommended
- CUDA 12.1+ toolkit (`nvcc --version` to verify)
- Python 3.11+

---

## Step 1 — Verify GPU is visible in WSL2

Open a WSL2 terminal and run:

```bash
nvidia-smi
```

You should see your GPU listed. If not, update your Windows NVIDIA driver (the driver ships CUDA for WSL2 — do not install CUDA separately inside WSL2 for the driver layer).

---

## Step 2 — Clone / access the repo in WSL2

The repo lives on your Windows filesystem. Access it from WSL2 at:

```bash
cd /mnt/c/Users/NEW\ LAP/Documents/repositories/waraq
```

Or clone a fresh copy inside WSL2's own filesystem for better I/O performance (optional):

```bash
git clone <your-remote-url> ~/waraq
cd ~/waraq
```

---

## Step 3 — Install Python dependencies in WSL2

```bash
# Install uv if not already present
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # or restart terminal

# Create venv and install project + vLLM server extras
uv venv
source .venv/bin/activate
uv pip install -e ".[server]"
```

> `[server]` installs `vllm>=0.4.0` in addition to the base project dependencies.

If uv's vllm install fails due to CUDA version mismatch, install vLLM directly:

```bash
pip install vllm --extra-index-url https://download.pytorch.org/whl/cu121
```

---

## Step 4 — Copy `.env` to WSL2 side (if running from WSL2 filesystem)

If you cloned inside WSL2, create a `.env` from the example:

```bash
cp .env.example .env
# Edit VLLM_BASE_URL, VLLM_MODEL if needed (defaults are correct for local setup)
```

---

## Step 5 — Start the vLLM server

```bash
bash scripts/start_vllm.sh
```

The first run downloads SILMA-9B from Hugging Face (~18 GB). Subsequent starts are fast.

You should see output ending with:

```
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

**Leave this terminal running.**

### Optional — GPU memory tuning

If you have a 16 GB card and the server OOMs:

```bash
bash scripts/start_vllm.sh --gpu-memory-utilization 0.80
```

If you want a shorter max context to save memory:

```bash
bash scripts/start_vllm.sh --max-model-len 4096
```

---

## Step 6 — Verify the server from Windows (optional quick check)

Open a PowerShell window on Windows and run:

```powershell
Invoke-RestMethod -Uri http://localhost:8001/v1/models -Method Get
```

You should see the model listed. WSL2 automatically bridges port 8001 to Windows localhost.

---

## Step 7 — Run the Stage 3 smoke test

From your **Windows** PowerShell (in the project directory):

```powershell
.venv\bin\python scripts\test_vllm.py
```

Or if you're running from inside WSL2:

```bash
python scripts/test_vllm.py
```

Expected output:

```
=== test_free_text ===
الأصول الثابتة هي...
PASSED

=== test_structured_output ===
{
  "intent": "valid",
  "reason": "..."
}
PASSED

All Stage 3 tests passed.
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `nvidia-smi` not found in WSL2 | GPU not exposed | Update Windows NVIDIA driver to ≥ 527.41 |
| `CUDA out of memory` at startup | VRAM too small | Lower `--gpu-memory-utilization` or `--max-model-len` |
| `Connection refused` on port 8001 | Server not started | Run `bash scripts/start_vllm.sh` in WSL2 first |
| `JSONDecodeError` from `structured()` | Model not following schema | Ensure vLLM version ≥ 0.4.0 (guided decoding support); check `guided_json` in `extra_body` |
| Import error for `waraq` | Package not installed | Run `uv pip install -e .` in the project root |
| Slow first response | Model cold-start / KV cache warming | Normal; subsequent calls are fast |

---

## What's next — Stage 4

Once the smoke test passes, Stage 4 (summary generation) can run. It reads `data/index.json`, extracts text for each leaf's page range from `data/parsed/output.json`, calls `client.complete()` to generate Arabic hooks, and writes them back into `data/index.json`.

Run (once implemented):

```bash
python scripts/run_summary_gen.py
```
