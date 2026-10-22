Kairos's issue-only context selector misses the file or function a fix needs. Trace one
development-bucket miss from issue text to final packed context (scripts/localization_dev024.py,
scripts/coding_context_v6_024.py), name the stage that lost it, and add a failing unit test that
reproduces the loss with synthetic source. Never read gold patches inside the selector and never
use exposed unseen023 cases. Keep v3 (scripts/coding_context_v3_014.py) byte-identical.
