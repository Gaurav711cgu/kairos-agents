"""F025 run-3 case selection: Verified, development bucket, unexposed, matching the pinned image version."""
import scripts.f025_cases as cases


def test_selects_verified_development_unexposed_matching_version(monkeypatch):
    monkeypatch.setattr(cases, 'bucket', lambda i: 'development' if i != 'django__django-3' else 'validation')
    rows = [{'instance_id': f'django__django-{n}', 'repo': 'django/django', 'version': v}
            for n, v in [(1, '3.1'), (2, '3.1'), (3, '3.1'), (4, '4.0'), (5, '3.1')]]
    assert cases.select_cases(rows, verified={'django__django-1', 'django__django-2', 'django__django-3', 'django__django-4'},
                              exposed={'django__django-2'}) == ['django__django-1']


def test_qualify_input_shape():
    assert cases.qualify_input(['a']) == {'jobs': [{'instance_id': 'a'}]}
