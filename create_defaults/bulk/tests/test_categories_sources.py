"""Batch source verification keeps exact-case/link/hash guarantees."""

import hashlib
from types import SimpleNamespace

import pytest

from create_defaults.bulk.common import BulkError,canonical
from create_defaults.bulk.contracts.categories import evidence


def record(inputs):
    return SimpleNamespace(to_dict=lambda:{"job_json":canonical({"inputs":inputs}).decode()})


def test_index_each_directory_once_and_verify_each_actual_hash(tmp_path,monkeypatch):
    assets=tmp_path/"M6-assets";assets.mkdir()
    inputs=[]
    for name in ("White.png","Black.png","Colour.png"):
        content=name.encode();(assets/name).write_bytes(content)
        inputs.append({"path":"M6-assets/"+name,"sha256":hashlib.sha256(content).hexdigest()})
    calls={};original=evidence.os.scandir
    def counted(path):
        calls[str(path)]=calls.get(str(path),0)+1
        return original(path)
    monkeypatch.setattr(evidence.os,"scandir",counted)
    assert evidence.verify_inputs([record(inputs),record(inputs)],tmp_path)=={i["path"]:i["sha256"] for i in inputs}
    assert all(count==1 for count in calls.values()) and len(calls)==2


@pytest.mark.parametrize("attack",["case","hash","traversal","conflict","link"])
def test_source_index_rejects_unsafe_or_changed_inputs(tmp_path,attack):
    source=tmp_path/"Logo.png";source.write_bytes(b"unchanged")
    inputs=[{"path":"Logo.png","sha256":hashlib.sha256(b"unchanged").hexdigest()}]
    if attack=="case":inputs[0]["path"]="logo.png"
    elif attack=="hash":source.write_bytes(b"changed")
    elif attack=="traversal":inputs[0]["path"]="../Logo.png"
    elif attack=="conflict":inputs.append(dict(inputs[0],sha256="a"*64))
    else:
        alias=tmp_path/"Linked.png"
        try:alias.symlink_to(source)
        except OSError:pytest.skip("Platform does not permit unprivileged symlink creation")
        inputs[0]["path"]="Linked.png"
    with pytest.raises(BulkError):evidence.verify_inputs([record(inputs)],tmp_path)


def test_directory_change_invalidates_the_cached_exact_name_index(tmp_path,monkeypatch):
    (tmp_path/"Logo.png").write_bytes(b"original")
    original=evidence.sha256
    def changed(path):
        value=original(path)
        (tmp_path/"Added.png").write_bytes(b"new directory entry")
        return value
    monkeypatch.setattr(evidence,"sha256",changed)
    with pytest.raises(BulkError):evidence.verify_inputs([record([{"path":"Logo.png","sha256":hashlib.sha256(b"original").hexdigest()}])],tmp_path)
