# Kairos: a five-minute review

Use the recorded demo first. It presents actual published evidence without requiring Docker, identity, model weights or inference. A separate full-stack journey demonstrates authenticated commands.

## Before the meeting

From the repository root, run `python3 -m scripts.reviewer demo`. Open the printed local URL. Check that the notice says “Recorded investigations. No live execution.” Keep `docs/CLAIMS_005.md` and the delivery acceptance receipt available. Do not depend on starting inference during the interview.

## The walkthrough

| Time | Show | Explain |
|---|---|---|
| 0:00–0:45 | Home page and the original Django investigation | The defect affected uploaded-file permissions. This is a historical source revision and a captured model attempt, not a fabricated demonstration. |
| 0:45–1:30 | Before/after change and independent check output | The candidate changes `FILE_UPLOAD_PERMISSIONS = None` to `0o644`. Download the patch and evidence. The captured run reports 110 tests and one skip. The reviewer can reproduce it separately. |
| 1:30–2:15 | Timeline, prepared context and check step | Show the issue, selected source and remaining budget. Explain source-bound edits, patch validation and immediate check feedback. Replay reads saved steps and does not execute the model or tools. |
| 2:15–3:00 | `/study` and one three-strategy comparison | Show zero verified repairs out of 36 evaluation attempts. More calls consumed additional inference without earning a better outcome here. Explain invalid patches, missing images, context limits and interrupted dispatches using their distinct outcomes. |
| 3:00–3:45 | `/capacity`, then the receipt | Show 435,270 requests over 42 minutes and the passing quiet soak. Keep the failed original soak visible. State that this is local control-plane traffic, separate from model and OIDC throughput. |
| 3:45–4:30 | Architecture and recovery evidence | Explain browser command identity, durable receipts, database-clock leases, fencing and content-addressed artifact storage. An uncertain provider response stays unknown; a stale worker cannot commit as the current owner. |
| 4:30–5:00 | Clean-checkout commands and claims table | Show the one entry point, explicit recorded/live modes, fresh acceptance receipt and reproducible repair command. Invite inspection of a concrete module or failure record. |

The final invitation is a chance to demonstrate ownership. Do not substitute memorized terminology for a trace through the code.

## Optional full-stack demonstration

Stop the demo with `python3 -m scripts.reviewer stop`, then run `python3 -m scripts.reviewer fullstack`. Use the locally generated admin account from the private credential file. Sign in through real Keycloak, queue a registered investigation, cancel it, create and cancel a fresh fork, replay its saved steps, publish it and download the bundle.

This default environment starts no inference worker. A queued record therefore stays queued until cancelled. Its purpose is to demonstrate identity, durable commands and evidence handling without model latency or surprise compute. The earlier frozen repair provides the independently reproducible patch demonstration.

Finish with `python3 -m scripts.reviewer stop`. It stops only owned reviewer services and preserves their volumes and the original installation.

## Prepare for follow-up questions

- Why does retrying a lost acknowledgement return the same investigation? Locate the browser’s pending-command journal and the database receipt check.
- What if the worker dies after the model received the request? Explain unknown dispatch, then contrast recovery after a captured response.
- Why does a lease need a fencing token? Describe the stale-worker commit that the token prevents.
- What does the artifact hash prove, and what can a privileged administrator still rewrite?
- Why did the new model study fail, and which failures describe infrastructure rather than model repair quality?
- Which measurements would be required before claiming production capacity or general repair competence?

An unfamiliar debugging exercise tests personal ownership separately. It is not a reason to delay delivering the tested software.
