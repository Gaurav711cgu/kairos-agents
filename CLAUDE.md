# Claude Code project instructions

Follow `AGENTS.md` first; this file only adds to it.

## Automatic session summary

After completing each user-requested task, end the response with one clearly marked,
copy-paste-friendly block titled **CHATGPT HANDOFF SUMMARY**. It covers everything from
immediately after the user's latest input until the end of execution:

1. Work completed: what was investigated, implemented or changed.
2. Files modified: important files and their changes.
3. Results: exact benchmarks, before/after metrics, tests passed/failed, regressions.
4. Problems: errors, blockers, unresolved issues, failed experiments.
5. Evidence: relevant logs, receipts, commit hashes, artifact paths.
6. Resources: model calls, token usage if measurable, downloads, Docker, external costs.
7. Current status: finished, running or pending.
8. Next steps: what should happen next and any approval required.

Rules: 250-350 words unless critical findings need more; exact numbers and technical details;
separate verified results from hypotheses; never claim tests passed unless executed; never omit
failures or negative results; self-contained so another AI can continue without the terminal
history; preserve Kairos benchmark separation (development / frozen validation / locked holdout)
and resource restrictions; keep Caveman and Ponytail full mode.
