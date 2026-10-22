from scripts.patch_roundtrip024 import classify, prefix_patch


def test_scope_guards_are_not_reported_as_pipeline_faults():
    assert classify(ValueError('Outside two-file/40-line source repair scope')) == 'scope_limit'
    assert classify(ValueError('Patch exceeds 200 changed lines')) == 'scope_limit'
    assert classify(ValueError('Reference edit is outside issue-only selected context; no answer-assisted expansion')) == 'outside_selected_context'
    assert classify(ValueError('Stale original-source digest')).startswith('pipeline_fault')


def test_prefix_patch_drops_tests_and_docs():
    patch = ('diff --git a/django/x.py b/django/x.py\n--- a/django/x.py\n+++ b/django/x.py\n@@ -1 +1 @@\n-a\n+b\n'
             'diff --git a/docs/y.txt b/docs/y.txt\n--- a/docs/y.txt\n+++ b/docs/y.txt\n@@ -1 +1 @@\n-a\n+b\n')
    assert prefix_patch(patch, 'django/') == patch.split('diff --git a/docs')[0]
