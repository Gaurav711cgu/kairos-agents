"""Development-only selected suites with explicit truncated-parameter expansion."""
from scripts.coding_verifier014 import test_ids, verifier as selected_verifier


def verifier(row):
    regression, existing = test_ids(row)
    expansions = []
    def expand(selector):
        # Dataset IDs cut at spaces cannot identify a parametrization. Run the
        # complete function instead; this increases coverage without guessing IDs.
        if '[' in selector and not selector.endswith(']'):
            parent = selector.split('[', 1)[0]
            if '::' not in parent:
                raise ValueError('Truncated parameter selector has no test function')
            expansions.append({'declared': selector, 'executed': parent})
            return parent
        return selector
    normalized = dict(row, FAIL_TO_PASS=sorted({expand(s) for s in regression}),
                      PASS_TO_PASS=sorted({expand(s) for s in existing}))
    script, scope = selected_verifier(normalized)
    scope.update(version='coding-selected-suite021-v1', declared_regressions=regression,
                 declared_existing=existing, parameter_expansions=expansions,
                 expansion_policy='Run every parametrization of truncated selectors; missing collection, skips and failures still reject qualification')
    return script, scope
