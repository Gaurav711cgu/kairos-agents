Confirm scripts/repair010/feedback010.py stays bounded: feedback never exceeds its byte budget,
oversized fields are omitted whole with hashes, and it never proposes a corrected edit. Add a test
for any uncovered bound. Do not add retries or change model budgets.
