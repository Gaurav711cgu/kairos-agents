"""Exposure scanning ignores this benchmark's own receipts and nothing else."""
import zipfile

from scripts.localization_dev024 import bucket, exposed_ids, targets


def test_own_receipts_do_not_expose_but_real_evidence_does(tmp_path):
    own = tmp_path / 'evidence/localization024/h1'
    own.mkdir(parents=True)
    (own / 'dev.json').write_text('{"case": "django__django-11111"}')
    other = tmp_path / 'evidence/closeout023'
    other.mkdir(parents=True)
    (other / 'report.json').write_text('django__django-22222')
    (tmp_path / 'evidence/localization024-copy.json').write_text('pytest-dev__pytest-3333')
    with zipfile.ZipFile(other / 'bundle.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('captures/x.json', 'pytest-dev__pytest-4444 ' * 50)
    found = exposed_ids([tmp_path], set(), {(tmp_path / 'evidence/localization024').resolve()})
    assert found == {'django__django-22222', 'pytest-dev__pytest-3333', 'pytest-dev__pytest-4444'}


def test_split_is_deterministic_and_scoring_labels_stay_in_prefix():
    assert bucket('django__django-11772') == bucket('django__django-11772')
    patch = 'diff --git a/django/db/x.py b/django/db/x.py\ndiff --git a/tests/t.py b/tests/t.py\ndiff --git a/docs/a.txt b/docs/a.txt\n'
    assert targets(patch, 'django/') == ['django/db/x.py']
