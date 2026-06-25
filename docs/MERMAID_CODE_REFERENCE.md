# Mermaid Render & Regen — Code Reference

Copy-paste map of the implementation. Paths relative to repo root.

**Narrative handoff:** [MERMAID_RENDER_AND_REGEN_HANDOFF.md](./MERMAID_RENDER_AND_REGEN_HANDOFF.md)

---

## Frontend — render

### `src/components/study/mermaidConfig.ts` — init, parse, render with retry

```ts
export function ensureMermaidInitialized(): void {
  if (initialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "neutral",
    securityLevel: "strict",
    flowchart: { useMaxWidth: true, htmlLabels: true, curve: "basis", padding: 12 },
    suppressErrorRendering: true,
  });
  initialized = true;
}

export async function renderMermaidSvg(diagramId: string, source: string): Promise<string> {
  const sanitized = sanitizeMermaidSource(source).trim();
  return runSerializedRender(() =>
    withQuietMermaidConsole(async () => {
      try {
        return await renderOnce(diagramId, sanitized);
      } catch (firstErr) {
        const aggressive = aggressiveSanitizeMermaidSource(sanitized).trim();
        if (aggressive !== sanitized) {
          try {
            return await renderOnce(`${diagramId}-agg`, aggressive);
          } catch { /* fall through */ }
        }
        throw new Error(friendlyMermaidError(firstErr));
      }
    }),
  );
}
```

### `src/components/study/MermaidBlock.tsx` — block UI + render hook

```tsx
function layoutSafeSource(source: string): string {
  return aggressiveSanitizeMermaidSource(sanitizeMermaidSource(source)).trim();
}

// useMermaidRender: validate → renderMermaidSvg → onHealed if sanitized ≠ file
const handleHealed = (healed: string) => {
  if (!handlersWithLang?.onBlockSave || editing) return;
  void handlersWithLang.onBlockSave(handlersWithLang.blockIndex, "mermaid", healed);
};
```

### `src/components/study/MarkdownNote.tsx` — block index (fenced only)

```tsx
code({ className, children, inline }) {
  if (inline) {
    return <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm">{children}</code>;
  }
  const blockIndex = blockCounter++;
  if (lang === "mermaid") {
    return (
      <Suspense fallback={<BlockFallback />}>
        <MermaidBlock code={code} sectionHandlers={sectionHandlersFor(blockIndex, "mermaid", sectionEdit)} />
      </Suspense>
    );
  }
  // ... python / other fenced blocks
}
```

---

## Frontend — sanitize (no LLM)

### `src/components/study/mermaidSanitize.ts` — aggressive canonical indexing diagram

```ts
export function aggressiveSanitizeMermaidSource(source: string): string {
  let out = sanitizeMermaidSource(source);
  out = out.replace(/\bW\s*\[[^\]]*\]/g, "index -1");
  // ... shorten labels ...
  if (/\bDirection\b/.test(out) && /Index|index/.test(out)) {
    return [
      "flowchart TD",
      "    A[Start] --> B{Direction}",
      "    B -->|L to R| C[Positive indices]",
      "    B -->|R to L| D[Negative indices]",
      "    D --> E[Last at index -1]",
      "    C --> F[Length minus one]",
    ].join("\n");
  }
  return out;
}
```

### `src/components/study/useSectionBlockEdit.tsx` — Fix syntax / Fix with AI

```tsx
const onSanitizeSyntax = useCallback(async () => {
  const source = editing ? draft : initialContent;
  const fixed = aggressiveSanitizeMermaidSource(sanitizeMermaidSource(source));
  await handlers.onBlockSave(handlers.blockIndex, handlers.language, fixed);
}, [...]);

const onRegenerate = useCallback(async () => {
  const fixed = await handlers.onBlockRegenerate(..., { mode: editing ? "polish" : "fix" });
  const polished = aggressiveSanitizeMermaidSource(sanitizeMermaidSource(fixed));
  if (regenerateAutoSave) await handlers.onBlockSave(..., polished);
}, [...]);
```

---

## Frontend — save & API

### `src/components/study/noteBlockUtils.ts` — replace fenced block

```ts
export function replaceFencedBlock(markdown: string, blockIndex: number, newContent: string): string {
  const blocks = listFencedBlocks(markdown);
  const block = blocks[blockIndex];
  if (!block) {
    throw new Error(
      `Could not save block ${blockIndex}: note has ${blocks.length} fenced block(s). Refresh and try again.`,
    );
  }
  const fence = `\`\`\`${block.lang}\n${newContent.trim()}\n\`\`\``;
  return markdown.slice(0, block.start) + fence + markdown.slice(block.end);
}
```

### `src/pages/study/LectureNotesPage.tsx` — handlers

```tsx
const handleBlockSave = useCallback(async (blockIndex, _language, newBlockContent) => {
  if (!selectedNote) throw new Error("No note selected — pick a file in the library first.");
  const base = repairNoteMarkdown(content);
  const blockBody =
    _language === "mermaid"
      ? aggressiveSanitizeMermaidSource(sanitizeMermaidSource(newBlockContent))
      : newBlockContent;
  const updated = replaceFencedBlock(base, blockIndex, blockBody);
  await saveNoteContent(selectedNote, updated);
  setContent(updated);
}, [content, selectedNote]);

const handleBlockRegenerate = useCallback(async (blockIndex, language, blockContent, error, opts) => {
  const result = await regenerateNoteBlock({
    block_type: language === "mermaid" ? "mermaid" : "code",
    language,
    content: blockContent,
    error,
    mode: opts?.mode ?? "fix",
    note_context: extractBlockSurroundingContext(repairNoteMarkdown(content), blockIndex, { blockContent }),
    llm: llmOverrides,
  });
  return result.content;
}, [content, llmProvider, llmBaseUrl, llmModel]);
```

### `src/api/transcriptsClient.ts` — LLM prefs + regenerate

```ts
const LLM_PREFS_KEY = "lecture-notes:llm";

export function loadLlmPrefs(): LlmOverrides {
  // defaults: lmstudio, http://127.0.0.1:1234, google/gemma-4-e4b
  // migrates gemini → lmstudio once (LLM_PREFS_MIGRATION_KEY v2)
}

export async function regenerateNoteBlock(opts: { ... }): Promise<{ content: string }> {
  const res = await fetch(`${BASE}/api/transcripts/library/regenerate-block`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      block_type: opts.block_type,
      content: opts.content,
      error: opts.error,
      mode: opts.mode ?? "fix",
      llm_provider: opts.llm?.llm_provider,
      llm_base_url: opts.llm?.llm_base_url,
      llm_model: opts.llm?.llm_model,
    }),
  });
  // ...
}

export async function saveNoteContent(relativePath: string, content: string): Promise<void> {
  await fetch(`${BASE}/api/transcripts/library/files/${encoded}/content`, {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify({ content }),
  });
}
```

---

## Backend — LLM + regenerate

### `backend/transcripts/mermaid_strict.py` — generation rules (in LLM prompt)

```python
MERMAID_GENERATION_RULES = """
- Edge labels MUST use pipe form only: A -->|Yes| B — never `A -- text --> B`.
- Never use stadium syntax id(label) — always id["label"].
- Inside labels write "index -1" — never W[-1] (breaks layout).
- Never use ellipsis `...` in labels — write "etc" instead.
- Diamond nodes: B{Direction} — never B{"Direction"}.
""".strip()
```

### `backend/transcripts/mermaid_strict.py` — aggressive sanitize

```python
def aggressive_sanitize_mermaid_source(source: str) -> str:
    out = sanitize_mermaid_source(source)
    out = re.sub(r"\bW\s*\[[^\]]*\]", "index -1", out)
    if re.search(r"\bDirection\b", out) and re.search(r"Index|index", out):
        return (
            "flowchart TD\n"
            "    A[Start] --> B{Direction}\n"
            "    B -->|L to R| C[Positive indices]\n"
            "    B -->|R to L| D[Negative indices]\n"
            "    D --> E[Last at index -1]\n"
            "    C --> F[Length minus one]"
        )
    return out
```

### `backend/transcripts/block_regenerate.py` — regenerate_block

```python
def regenerate_block(*, block_type, language, content, error=None, mode="fix", llm=None) -> str:
    if not ollama_available(llm):
        raise RuntimeError("LLM is not reachable...")
    prompt = _build_prompt(block_type=block_type, language=language, content=content, error=error, mode=mode, ...)
    raw = ollama_generate(
        prompt,
        timeout=90.0,
        llm=llm,
        system_prompt="You output raw source code or diagram text only. Never wrap in markdown fences.",
    )
    cleaned = _strip_fences(raw)
    if block_type == "mermaid":
        cleaned = sanitize_mermaid_source(cleaned)
        cleaned = aggressive_sanitize_mermaid_source(cleaned)
    return cleaned.strip()
```

### `backend/core/ollama_client.py` — LM Studio

```python
def _lmstudio_generate(prompt, *, opts, timeout, system_prompt=None) -> str | None:
    payload = {
        "model": opts.model,
        "input": prompt,
        "reasoning": "off",
    }
    if system_prompt:
        payload["system_prompt"] = system_prompt
    url = f"{_openai_api_base(opts.base_url)}/chat"
    # POST; on 400 retry without reasoning
    # parse output[].type == "message" → content
```

### `backend/transcripts/router.py` — routes

```python
@router.get("/llm-config")
def get_llm_settings(llm_provider=None, llm_base_url=None, llm_model=None, ...):
    # returns { reachable, provider, base_url, model }

@router.post("/library/regenerate-block")
def regenerate_note_block(body: RegenerateBlockRequest, ...):
    # logs provider/model; calls regenerate_block()

@router.put("/library/files/{relative_path:path}/content")
def put_library_file_content(relative_path, body, ...):
    # save_note_content() → writes data/notes/{path}
```

### `backend/transcripts/note_block_repair.py` — batch

```python
def repair_all_blocks(markdown, *, use_llm=True, llm=None):
    # 1. sanitize all mermaid fences locally
    # 2. if use_llm: regenerate_block() per still-broken mermaid/code block
    # returns (fixed_markdown, details)
```

---

## Backend — note generation (prevent bad mermaid at source)

### `backend/transcripts/notes_generator.py`

Embeds `MERMAID_GENERATION_RULES` in chunk prompts and runs `sanitize_mermaid_blocks()` before saving generated notes.

---

## Tests to run after changes

```bat
npx vitest run tests/test_mermaid_sanitize.test.ts tests/test_note_block_utils.test.ts
python -m pytest tests/test_mermaid_strict.py tests/test_note_block_repair.py tests/test_block_regenerate.py -q
```

Key test cases:

- `test_aggressive_sanitize_gemma_output_uses_canonical_indexing_flow` (Python)
- `replaceFencedBlock` throws on out-of-range index (TS)
- Edge label `-- text -->` → `-->|text|` (both languages)

---

## Sample broken input (user note)

File: `data/notes/live_captions_20260623_204143_20260624_030551.md`  
First mermaid block (~line 41) — indexing Direction diagram with `W[-1]`, `...`, long labels.

See [STUDY_LIBRARY_MERMAID_SAMPLE_BROKEN.md](./STUDY_LIBRARY_MERMAID_SAMPLE_BROKEN.md) for isolated fixtures.
