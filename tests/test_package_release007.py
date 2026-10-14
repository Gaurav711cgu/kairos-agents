"""Publication boundaries use isolated tiny packages, never real credentials."""
import io
import json
from pathlib import Path
import tarfile
import pytest
from scripts.package_release007 import (fingerprint, inventory, seal, verify, verify_archive, safe_name, scan_private_values)

@pytest.fixture
def package(tmp_path):
    root=tmp_path/'source';root.mkdir()
    (root/'app.py').write_text('print("reviewable")\n')
    out=root/'evidence/build007';out.mkdir(parents=True)
    (out/'final-checks.json').write_text(json.dumps({'release':'build007','passed':True,'checks':{'unit':{'passed':True,'returncode':0}}}))
    original=tmp_path/'original.tar.gz';original.write_bytes(b'Preserved external historical archive fixture')
    return root,original

def test_seal_binds_source_acceptance_archive_and_preserved_history(package):
    root,original=package
    private=root/'.runtime';private.mkdir();(private/'secret').write_text('excluded fixture')
    receipt=seal(root,original_archive=original,private_files=[])
    assert receipt['passed'] and not receipt['external_publication_performed']
    assert verify(root,original_archive=original,private_files=[])['archive_checked']
    assert not any('.runtime' in name for name in inventory(root))
    with pytest.raises(ValueError,match='already exists'):seal(root,original_archive=original,private_files=[])

@pytest.mark.parametrize('change',['source','acceptance','archive','history','manifest'])
def test_altered_release_binding_is_rejected(package,change):
    root,original=package;seal(root,original_archive=original,private_files=[])
    targets={'source':root/'app.py','acceptance':root/'evidence/build007/final-checks.json','archive':root/'evidence/build007/publication.tar.gz','history':original,'manifest':root/'evidence/build007/manifest.json'}
    path=targets[change];path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError):verify(root,original_archive=original,private_files=[])

def test_failed_acceptance_cannot_be_sealed(package):
    root,original=package
    path=root/'evidence/build007/final-checks.json';value=json.loads(path.read_text());value['checks']['unit']['passed']=False;path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='incomplete or failed'):seal(root,original_archive=original,private_files=[])
    assert not (root/'evidence/build007/publication.tar.gz').exists()

@pytest.mark.parametrize('name',['../outside','/outside','a/../b','a//b','a\\b'])
def test_ambiguous_member_names_rejected(name):
    with pytest.raises(ValueError):safe_name(name)

@pytest.mark.parametrize('kind',['duplicate','traversal','symlink','corrupt','missing'])
def test_unsafe_or_incomplete_archive_rejected(tmp_path,kind):
    data=b'original';expected_file=tmp_path/'app.py';expected_file.write_bytes(data);expected={'app.py':fingerprint(expected_file)}
    archive=tmp_path/'bad.tar.gz'
    with tarfile.open(archive,'w:gz') as output:
        names=[] if kind=='missing' else ['kairos/../outside'] if kind=='traversal' else ['kairos/app.py']*(2 if kind=='duplicate' else 1)
        for name in names:
            member=tarfile.TarInfo(name)
            if kind=='symlink':member.type=tarfile.SYMTYPE;member.linkname='../outside';output.addfile(member)
            else:
                body=b'changed!' if kind=='corrupt' else data;member.size=len(body);output.addfile(member,io.BytesIO(body))
    with pytest.raises(ValueError):verify_archive(archive,expected)

def test_private_value_scan_rejects_included_bytes_without_printing_value(package):
    root,_=package;value=b'isolated-fixture-secret-123'
    (root/'leak.log').write_bytes(b'prefix '+value+b' suffix')
    with pytest.raises(ValueError,match='leak.log') as error:scan_private_values(root,inventory(root),{value})
    assert value.decode() not in str(error.value)

def test_symbolic_source_escape_is_rejected(package):
    root,original=package;(root/'escape.py').symlink_to(original)
    with pytest.raises(ValueError,match='Symlink|escaped'):inventory(root)


def test_preserved_oversized_raw_is_verified_against_lossless_index(package,monkeypatch):
    import scripts.package_release007 as publication
    root,_=package
    raw=root/'evidence/build004/capacity-pooled-run.txt';raw.parent.mkdir(parents=True);raw.write_bytes(b'x'*2048)
    index=root/'evidence/build005/historical-raw-index.json';index.parent.mkdir(parents=True)
    index.write_text(json.dumps({'members':{'evidence/build004/capacity-pooled-run.txt':fingerprint(raw)}}))
    monkeypatch.setattr(publication,'MAX_MEMBER_BYTES',1024)
    assert 'evidence/build004/capacity-pooled-run.txt' not in inventory(root)
    assert 'evidence/build005/historical-raw-index.json' in inventory(root)
    raw.write_bytes(b'changed raw measurement')
    with pytest.raises(ValueError,match='differs from lossless index'):inventory(root)


def test_unindexed_oversized_raw_cannot_be_hidden(package,monkeypatch):
    import scripts.package_release007 as publication
    root,_=package
    raw=root/'evidence/build004/capacity-pooled-run.txt';raw.parent.mkdir(parents=True);raw.write_bytes(b'x'*2048)
    monkeypatch.setattr(publication,'MAX_MEMBER_BYTES',1024)
    with pytest.raises(ValueError,match='100 MiB'):inventory(root)


def test_private_api_key_scan_catches_accidental_included_value(package):
    from scripts.package_release007 import private_values
    root,_=package
    path=root/'.runtime/free-model-pilot/environment.env';path.parent.mkdir(parents=True)
    secret='isolated-fixture-api-key-007'
    path.write_text('GEMINI_API_KEY='+secret+'\n');path.chmod(0o600)
    (root/'accidental-response.txt').write_text(secret)
    with pytest.raises(ValueError,match='accidental-response.txt') as error:
        scan_private_values(root,inventory(root),private_values([path]))
    assert secret not in str(error.value)
