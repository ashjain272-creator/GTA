"""URL acquisition (AM-29): rights preconditions and forbidden downloader options.
The live YouTube download itself is NOT exercised here (no network access to YouTube
in CI or the dev container); the end-to-end flow is tested with a named mock downloader."""
from __future__ import annotations

import socket
import sys
import types
from pathlib import Path

import pytest

from clipops import config
from clipops.ingest.acquire import FORBIDDEN_KEYS, check_preconditions, ydl_options
from clipops.runreport import StageFailed

CFG = config.load(Path(__file__).resolve().parents[2])
URL = "https://www.youtube.com/watch?v=abc123XYZ00"


@pytest.mark.parametrize("klass", ["E", "F", "C", "D"])   # E without attestation
def test_only_classes_a_and_b_can_be_acquired(klass, monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    with pytest.raises(StageFailed):
        check_preconditions(URL, klass, None)


def test_class_b_requires_written_grant():
    with pytest.raises(StageFailed, match="grant"):
        check_preconditions(URL, "B", None)
    assert check_preconditions(URL, "B", {"document_ref": "grants/creator.pdf", "scope": {}})["object_id"] == "abc123XYZ00"


def test_channel_and_playlist_rules():
    ch, pl = "https://www.youtube.com/@SomeCreator", "https://www.youtube.com/playlist?list=PL1"
    assert check_preconditions(ch, "A", None)["multi"] is True                 # own channel
    with pytest.raises(StageFailed, match="crawl_refused|channels/playlists"):
        check_preconditions(ch, "E", None, attestation="commentary")           # no crawling without rights
    with pytest.raises(StageFailed, match="channels/playlists"):
        check_preconditions(pl, "B", {"document_ref": "g", "scope": {}})        # grant must cover it
    assert check_preconditions(pl, "B", {"document_ref": "g", "scope": {"collections": [pl]}})["multi"]
    with pytest.raises(StageFailed, match="not supported"):
        check_preconditions("https://www.twitch.tv/videos/123", "A", None)


def test_class_e_needs_attestation():
    with pytest.raises(StageFailed, match="attest"):
        check_preconditions(URL, "E", None)
    assert check_preconditions(URL, "E", None, attestation="commentary; fair-use claim")["multi"] is False


def test_cookies_only_from_operator_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CLIPOPS_YOUTUBE_COOKIES_FILE", raising=False)
    assert "cookiefile" not in ydl_options(tmp_path, CFG)
    f = tmp_path / "cookies.txt"
    f.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("CLIPOPS_YOUTUBE_COOKIES_FILE", str(f))
    assert ydl_options(tmp_path, CFG)["cookiefile"] == str(f)
    monkeypatch.setenv("CLIPOPS_YOUTUBE_COOKIES_FILE", str(tmp_path / "missing.txt"))
    with pytest.raises(StageFailed, match="missing"):
        ydl_options(tmp_path, CFG)


def test_downloader_options_exclude_evasion_and_credentials(tmp_path):
    opts = ydl_options(tmp_path, CFG)
    assert not (FORBIDDEN_KEYS & set(opts))
    assert {"proxy", "impersonate", "source_address"} <= FORBIDDEN_KEYS     # evasion stays impossible
    assert opts["noplaylist"] is True and opts["allow_unplayable_formats"] is False
    assert ydl_options(tmp_path, CFG, multi=True)["playlistend"] == CFG["acquire"]["max_items"]
    assert opts["ratelimit"] > 0


def test_flow_with_mock_downloader_records_provenance(tmp_path, monkeypatch):
    class MockYoutubeDL:                                    # test double, named as such
        def __init__(self, opts):
            self.opts = opts
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download):
            out = Path(self.opts["outtmpl"].replace("%(id)s", "abc123XYZ00").replace("%(ext)s", "mp4"))
            out.write_bytes(b"fake media")
            return {"id": "abc123XYZ00", "title": "t", "uploader": "u", "channel_id": "c", "format_id": "137+140",
                    "webpage_url": url}
        def prepare_filename(self, info):
            return self.opts["outtmpl"].replace("%(id)s", info["id"]).replace("%(ext)s", "webm")
    mock = types.SimpleNamespace(YoutubeDL=MockYoutubeDL, version=types.SimpleNamespace(__version__="mock"))
    monkeypatch.setitem(sys.modules, "yt_dlp", mock)
    from clipops.orchestrator.pipeline import Pipeline
    from clipops.runreport import RunReport
    from clipops.storage.artefacts import read_json
    cfg = config.load(overrides={"paths": {"work": str(tmp_path / "w"), "sources": str(tmp_path / "s")}})
    rep = RunReport(cfg, "mock acquire")
    [sid] = Pipeline(cfg, rep).add_url(URL, "A", game="Grand Theft Auto V", grant=None)
    rec = read_json(tmp_path / "w" / sid / "rights.json")
    assert rec["platform"] == "youtube" and rec["origin_url"] == URL
    assert rec["monetisation_allowed"] == "no"                      # Rockstar policy still applies
    assert "AM-29" in rec["notes"]
    # class E with an attestation: accepted, monetisation forced off, attestation stored
    (tmp_path / "s" / "url" / "abc123XYZ00.mp4").write_bytes(b"other fake media")
    [sid_e] = Pipeline(cfg, RunReport(cfg, "e")).add_url(URL, "E", game=None, grant=None,
                                                          attestation="commentary; fair-use claim")
    rec_e = read_json(tmp_path / "w" / sid_e / "rights.json")
    assert rec_e["class"] == "E" and rec_e["monetisation_allowed"] == "no"
    assert rec_e["operator_attestation"] == "commentary; fair-use claim"
    assert any(w["code"] == "tos_risk" for w in rep.data["warnings"])
