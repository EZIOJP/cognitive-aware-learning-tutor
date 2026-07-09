# Local LLM guide — lecture notes (CPU-friendly, quality)

Use this with **Transcript Notes Studio** and **LM Studio** (or Ollama) on your PC.

## CPU vs GPU — what loads what

| Step | Mostly uses | Notes |
|------|-------------|--------|
| **Parse** (Tune) | **CPU** | Regex dedup; parse-speed slider cools CPU |
| **Whisper** (Capture) | **GPU** if `device=auto` | Set Whisper to CPU in Studio if GPU is busy |
| **Generate notes** | **GPU or CPU** | Depends on LM Studio offload settings |
| **Semantic chunking** | **CPU** (+ small embed model) | Off by default on huge transcripts |

**Your ask:** less GPU, more CPU for notes → in **LM Studio** load a **smaller quantized model** and set **GPU layers = 0** (CPU-only). Slower per chunk, but frees the GPU for Whisper/other apps.

## Model picks (local, notes quality)

| Goal | Model examples | Quant | RAM hint |
|------|----------------|-------|----------|
| **Best quality / patient** | `google/gemma-3-12b-it` or `llama-3.1-8b-instruct` | Q4_K_M | 16–24 GB |
| **Balanced (your current class)** | `google/gemma-3-4b-it` | Q4_K_M | 8–12 GB |
| **CPU-only, slow OK** | `llama-3.2-3b-instruct` or `gemma-3-4b-it` | Q4_K_M | 8 GB |
| **Avoid for 2h lectures** | `gemma-4-e4b` huge / mostly GPU | — | Very slow or OOM on CPU |

In Studio **Generate** step, set **Model** to the **exact id** LM Studio shows under **Local Server** (e.g. `google/gemma-3-4b-it`).

### LM Studio settings (CPU-heavy)

1. Download **Q4_K_M** (or Q5) — not F16.
2. **Context length:** 8192–16384 (notes chunks are large).
3. **GPU offload:** `0` layers for CPU-only, or `10–20` for partial GPU if you have VRAM.
4. **Temperature:** `0.3` (Studio default) — good for structured notes.

### Ollama alternative

```bat
ollama pull llama3.2:3b
```

Studio: provider `ollama`, URL `http://127.0.0.1:11434`, model `llama3.2:3b`.

## Studio quality presets (Generate step)

| Preset | Passes | Speed | Use when |
|--------|--------|-------|----------|
| **Fast** | ~8–12 | Quick | Draft only |
| **Balanced** | ~20 | Medium | Default |
| **Quality** | ~28+ | Slow | You want coverage; OK waiting hours |
| **Overnight** | ~20 | Paused | Sleep batch: tune + text-only + RAG |

Also: **Parse on Tune** first, **Include diagrams OFF** for overnight, **`max_llm_chunks`: 24–28** in `config.json`.

**LLM pause (sec)** between chunks — spreads CPU heat; set `2`–`5` for cool runs (overnight preset uses 3s).

## Division of labor (Studio vs web)

```text
Studio  = Capture → Tune → (optional) local generate · Auto/overnight batch
Web     = RAG notes → Quiz → Export PDF/Word → SRS
Overnight = Studio auto batch: Tune + text-only generate + corpus handoff
```

After Studio saves notes, open **Study Library** (`http://localhost:5173/lecture-notes?file=...`) for quiz and export.

## How the pipeline generates notes (text first, visuals last)

Per-chunk LLM passes are **text-only** — headings, bullets, definitions. No mermaid or code
is requested mid-stream. After all chunks are merged, one **visual enrich pass** adds
mermaid diagrams and code blocks where the text warrants them (batched by `##` section on
long documents, with a guard that keeps original text if the model drops content).
Fast mode skips the enrich pass entirely, giving text-only notes.

## Tiers and cloud fallback (web app)

The backend routes every LLM call through a **tiered gateway** (see
[LLM_GATEWAY.md](./LLM_GATEWAY.md)). In the web Study Library header you pick a tier:

| Tier | Typical chain | Use for |
|------|---------------|---------|
| **light** | small local model | coach chat, classification |
| **medium** | local Gemma → cloud fallback | notes chunks, quiz, drills (default) |
| **heavy** | cloud (Gemini/Claude) → local fallback | corpus-grounded synthesis |

Heavy tier has a **daily soft cap** — when it is reached the UI asks for confirmation before
continuing with cloud calls. If a provider in the chain fails, the gateway falls back to the
next one and the toast after the job shows which provider actually served it.
Chains are configured in `data/llm_tiers.json` or `.env` (`LLM_TIER_*`).

Notes Studio (the desktop app) uses its own provider settings from the Generate step and is
unaffected by tiers.

## CPU temperature in the app

Studio shows **CPU °C** in the top bar when Windows exposes ACPI thermal sensors (PowerShell/WMI). Many laptops report **n/a** — use **HWiNFO** or **Core Temp** alongside Studio. Parse-speed slider still reduces parse CPU load.

## Export for insights

After a run, **Done → Export insights…** saves:

- Notes `.md`, source/cleaned transcript, cleanup + notes audits, config snapshot, log tail

Full code handoff:

```bat
scripts\export_transcript_studio_handoff.bat
```

See [TRANSCRIPT_STUDIO_HANDOFF.md](./TRANSCRIPT_STUDIO_HANDOFF.md).

## Realistic expectations

Local models **summarize** — they will not produce a 112k-word verbatim transcript. After the chunk-size fix, **more LLM passes = more topics covered**, not a perfect lecture clone. Use **Notes audit** tab to see retention %.
