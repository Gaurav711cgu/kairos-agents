Rejected source-handle edits only say "Candidate Python syntax rejected at line N". Add a
deterministic classification of the rejection (indentation shift versus the original start line,
range ending on a block opener, range outside the captured excerpt, no-op) without repairing or
rewriting model output. Cover each class with a unit test using synthetic edits.
