# Kairos build006: five-minute demonstration

Start `python3 -m scripts.reviewer demo`, then open `http://127.0.0.1:3310`. Docker and inference can stay off.

1. **0:00–1:00 — The problem and proposal.** Open the featured Django11066 development investigation. Identify the pinned revision and public issue, including its repair hint. Explain the original multi-database save behavior and read the proposed diff.
2. **1:00–2:00 — Evidence and checks.** Inspect retained original source and the exact selected context using the keyboard. Show the passing registered checks. Download the original evidence and patch. This case has its own small test scope; do not call it the separate 110-test repair.
3. **2:00–3:00 — Failures and comparative cost.** Open Repair results. Show all 28 new attempts, fresh 0/10 and preserved old 0/36. Compare calls/tokens/checks and explain the unknown-dispatch usage caveat. All six development successes cover one issue-hinted case.
4. **3:00–4:00 — Engineering.** Open Engineering. Trace command identity, durable acceptance, database-clock fencing, source handles and execution-free replay. Explain the diagnosed 55/66 source-context failure and why a harness fix cannot guarantee model success.
5. **4:00–5:00 — Reproduction and measured reliability.** Open Docs and Capacity. Show the one reviewer entry point, 42-minute local measurement and original failed soak. Identify the separate recorded Django10914 reproduction receipt: 110 tests, one skip, disclosed image change. Conclude with exact scope: local full-stack infrastructure, not production-scale or general repair competence.

For an authenticated demonstration, stop recorded mode and run `python3 -m scripts.reviewer fullstack`. Use generated local accounts to show queue/cancel/fork/replay and viewer/tenant denial. Inference and workers remain off unless explicitly prepared. Stop owned services afterward; preserve volumes.
