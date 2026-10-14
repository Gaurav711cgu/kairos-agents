"""Object recovery boundaries; fixture archives contain no user or model data."""
import hashlib
import io
import json
import stat
import tarfile

import pytest

from scripts.verify_operations import _blob_bytes, _private_file, _restore_blob_archive


def archive_at(path,members):
    with tarfile.open(path,"w:gz") as backup:
        for name,data,kind in members:
            member=tarfile.TarInfo(name)
            if kind=="link":
                member.type=tarfile.SYMTYPE
                member.linkname="../outside"
                backup.addfile(member)
            else:
                member.size=len(data)
                backup.addfile(member,io.BytesIO(data))
    return path


def test_restore_object_archive_verifies_bytes_and_private_permissions(tmp_path):
    data=json.dumps({"raw_response":"exact fixture capture"}).encode()
    key=hashlib.sha256(data).hexdigest()
    archive=archive_at(tmp_path/"objects.tar.gz",[(key,data,"file")])
    destination=tmp_path/"restored"
    assert _restore_blob_archive(archive,destination,{key})=={key}
    assert _blob_bytes(destination,key)==data
    assert stat.S_IMODE((destination/key).stat().st_mode)==0o600
    assert stat.S_IMODE(destination.stat().st_mode)==0o700


@pytest.mark.parametrize("kind",["traversal","link","duplicate","corrupt","missing","unreferenced"])
def test_restore_refuses_unbound_or_unsafe_archive_entries(tmp_path,kind):
    data=b'{"fixture":true}'
    key=hashlib.sha256(data).hexdigest()
    entries=[(key,data,"file")]
    expected={key}
    if kind=="traversal":
        entries=[("../outside",data,"file")]
    elif kind=="link":
        entries=[(key,b"","link")]
    elif kind=="duplicate":
        entries*=2
    elif kind=="corrupt":
        entries=[(key,b'{"changed":true}',"file")]
    elif kind=="missing":
        entries=[]
    else:
        expected=set()
    archive=archive_at(tmp_path/"bad.tar.gz",entries)
    with pytest.raises(ValueError):
        _restore_blob_archive(archive,tmp_path/"restore",expected)
    assert not (tmp_path/"outside").exists()


def test_backup_creation_is_private_and_never_overwrites_existing_file(tmp_path):
    path=tmp_path/"private.dump"
    with _private_file(path) as output:
        output.write(b"fixture")
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    with pytest.raises(FileExistsError):
        _private_file(path)
    assert path.read_bytes()==b"fixture"
