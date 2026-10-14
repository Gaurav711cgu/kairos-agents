# Build004 repair study

Eighteen new historical cases qualified: six Django, six pytest and six Requests. Two cases per repository were used for development; four were locked for evaluation. Selection followed instance-ID order with exclusions recorded before model execution. Source regions were human-localized using maintainer patch locations; this assistance is disclosed and means the task is not unrestricted repository localization. Public cases may be present in training data.

Both local model profiles were compared on the same six development cases. Selection used verified repairs, invalid responses and elapsed time, in that order. Model/profile hashes and scores are in `profile-selection.json`. The Lenovo was not connected or measured. Two development revisions were used; the selected configuration then froze before evaluation. Each of twelve evaluation cases was run once under each of three strategies.

| Strategy | Verified / 12 | Calls | Captured tokens | Elapsed, seconds |
|---|---:|---:|---:|---:|
| baseline-v4 | 0 | 11 | 25714 | 190.7 |
| loop-v4 | 0 | 66 | 70544 | 160.7 |
| drafts-v4 | 0 | 64 | 149067 | 542.2 |

Single call receives one draft and one check. The tool loop receives six calls, two applied patches and two checks with immediate feedback. Independent drafts receive six fresh-context calls, selecting the first two structurally valid candidates before either check. Every captured draft and rejected or unselected result remains in the ledger. Six is the ceiling; interrupted attempts may capture fewer. The two multi-call strategies share ceilings, not guaranteed equal actual compute. All strategies have a ten-minute limit.

{
  "target_cases": 6,
  "target_repositories": 2,
  "actual_cases": 0,
  "actual_repositories": 0,
  "met": false
}

The quality target is reported, not guaranteed. Missing it does not erase engineering checks or justify tuning on evaluation cases. Paired differences and repository-stratified bootstrap intervals describe resampling of this small curated sample. They do not establish broad competence, model research, statistical superiority or a SWE-bench leaderboard result. Captured tokens exclude consumption from unknown responses. Duration sums exclude interrupted attempts whose stored timestamps do not capture recovery; consult the reboot receipt for that limitation.

Verification requires a reproduced baseline failure, passing regression and selected existing tests after the model patch, and a complete nonzero test-run marker. Candidate Python shares the verifier container environment with the checks. Adversarial test-forgery resistance is not established. Reference repairs were used only for qualification and never counted as agent results.

Inspect `attempt-ledger.json`, the frozen evaluation lock, original model actions, generated patches and check captures. Original build003 results and earlier failed pilots remain separate and unchanged.
