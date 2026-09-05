# Quality Records & Review Area for Antigravity / Gemini

This area stores backend Q&A interaction records for `/ask` and `/nrl` commands so that you (the admin) can have Antigravity or Gemini review answer quality, rate answers with **[YES]** or **[NO]**, and track areas of improvement over time.

---

## 📁 Directory Structure

```
data/quality_records/
├── pending.jsonl       # Unreviewed interactions awaiting evaluation
├── processed.jsonl     # Historical archive of evaluated interactions
├── reviews/            # Generated Markdown review scorecards
└── README.md           # Instructions for Antigravity & Gemini
```

---

## 🤖 Instructions for Antigravity / Gemini

When the user asks to **"review quality"**, **"run quality check"**, or **"review recent answers"**:

1. **Read Unreviewed Records**:
   - Read lines from `data/quality_records/pending.jsonl` (or call `quality_service.get_pending_records()`).
   - If `pending.jsonl` is empty, report that all interactions have been reviewed.

2. **Evaluate Each Record ([YES] / [NO])**:
   - **[YES]**: The answer is accurate, factually sound, respects 7-day temporal freshness, and correctly references reality (e.g. correct player club, correct round status).
   - **[NO]**: The answer contains hallucinations (e.g. Cobbo returning to Broncos), outdated facts, wrong statistics, or irrelevant sources.
   - For any **[NO]**, provide root-cause analysis (e.g., *Temporal Hallucination*, *Missing Player Stats*, *Web Search Rate Limit*).

3. **Generate Markdown Review & Archive**:
   - Call `quality_service.generate_quality_review_report(evaluations)` in Python, or format a report into `reviews/quality_review_<YYYY-MM-DD>.md`.
   - Call `quality_service.archive_records(record_ids, evaluations)` to move evaluated records into `processed.jsonl`.
   - The evaluated items will be removed from `pending.jsonl`, ensuring old information is never re-reviewed!
