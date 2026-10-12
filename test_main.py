import json
import time

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    main._hits.clear()
    return TestClient(main.app)


def up(client, data=b"\x00ciphertext", **params):
    return client.post("/api/files", content=data, params=params)


def test_roundtrip(client):
    r = up(client, b"hello-encrypted", max_downloads=3)
    assert r.status_code == 201
    fid = r.json()["id"]
    got = client.get(f"/api/files/{fid}")
    assert got.status_code == 200 and got.content == b"hello-encrypted"


def test_one_time_link_dies_after_first_download(client):
    fid = up(client).json()["id"]
    assert client.get(f"/api/files/{fid}").status_code == 200
    assert client.get(f"/api/files/{fid}").status_code == 404


def test_expired_link_is_deleted(client, tmp_path):
    fid = up(client).json()["id"]
    meta_path = tmp_path / f"{fid}.json"
    meta = json.loads(meta_path.read_text())
    meta["expires_at"] = time.time() - 1
    meta_path.write_text(json.dumps(meta))
    assert client.get(f"/api/files/{fid}").status_code == 404
    assert not (tmp_path / f"{fid}.bin").exists()


def test_too_large_rejected(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_BYTES", 10)
    assert up(client, b"x" * 11).status_code == 413


def test_empty_and_bad_ids(client):
    assert up(client, b"").status_code == 400
    assert client.get("/api/files/../../etc/passwd").status_code == 404
    assert client.get("/api/files/" + "g" * 32).status_code == 404


def test_server_stores_only_what_it_was_sent(client, tmp_path):
    fid = up(client, b"opaque-bytes").json()["id"]
    assert (tmp_path / f"{fid}.bin").read_bytes() == b"opaque-bytes"
    assert set(json.loads((tmp_path / f"{fid}.json").read_text())) == {
        "expires_at", "max_downloads", "downloads", "size"}  # no key, no filename


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(main, "RATE_LIMIT", 3)
    codes = [up(client).status_code for _ in range(4)]
    assert codes == [201, 201, 201, 429]