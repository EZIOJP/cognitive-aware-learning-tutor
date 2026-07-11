# Google Deep Research — CALT lecture notes (assemble vs LLM)

Paste into Google Deep Research / Gemini Deep Research. Goal: design a **reliable local notes pipeline** that does **not** depend on freeform LLM rewriting of noisy live captions.

## Context

I have a local-first study app (Cognitive-Aware Learning Tutor):

- Input: noisy Windows Live Captions / Whisper transcripts of data-science lectures (NumPy, DAV, Scalar platform).
- Corpus: textbooks ingested into hybrid RAG (BM25 + dense vectors), filtered to `source_type=textbook` for notes.
- Pain: multi-pass LLM notes (concept extract → RAG → narrative/sequential rewrite → refine → mermaid enrich) produce Definition/Importance templates, classroom UI sections, and broken code fences — even with DROP rules in prompts.
- Desired: **Assemble mode** = programming + retrieval: segment transcript → retrieve textbook passages → extractive lecture bullets + quoted cites — **no LLM rewrite**. Optional tiny polish later.

## Research questions

1. **Best extractive / retrieval-augmented note assembly** for lecture revision (not meeting minutes): topic segmentation without LLM, query formulation from noisy ASR, how many textbook passages per topic, how to present cites for study.
2. **What should stay code vs LLM?** Logistics filtering, outline detection, citation assembly, mermaid templates — vs one optional short polish pass.
3. **Evaluation**: cheap automatic metrics (citation coverage, logistics leakage rate, template-section rate, claim–evidence spot checks) that work offline.
4. **Failure modes** when dense retrieval falls back to SQLite / BM25-only; how to keep notes useful.
5. **Prior art**: extractive summarization for education, RAG-without-generation, “notes as evidence packs,” Sketchy/Anki-style concept cards from textbooks.

## Constraints

- Local-first; small models (Gemma 4B / GPT-4o-mini) are unreliable for long structured rewrite.
- Notes must brief **topics taught**, grounded in textbooks — not speaker diary or LMS UI.
- Mermaid/code enrich is optional and often harmful; prefer template diagrams or none.

## Deliverable format

1. Recommended **pipeline stages** (ordered) with “code” vs “LLM” labels.
2. Concrete **algorithms** for topic segmentation + query building from live captions.
3. A **minimal Assemble markdown schema** (headings, bullets, cite blocks).
4. An **eval checklist** I can run after each generate.
5. What **not** to do (anti-patterns matching Definition dumps / sequential full-doc rewrite / visual enrich on every section).

## Success criteria

A student can revise from Assemble notes in one pass: topics in lecture order, each with short lecture evidence + textbook quote + cite id — without encyclopedia templates or session logistics.
