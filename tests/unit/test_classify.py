"""Spec 4.15 test 1: a class E URL causes no download, states the limitation,
and produces a permission-request draft."""
from __future__ import annotations

import socket

import pytest

from clipops.ingest.classify import class_e_outcome, classify_url


@pytest.mark.parametrize("url,platform,obj,oid", [
    ("https://www.youtube.com/watch?v=abc123", "youtube", "video", "abc123"),
    ("https://youtu.be/abc123", "youtube", "video", "abc123"),
    ("https://www.youtube.com/@SomeCreator", "youtube", "channel", "@SomeCreator"),
    ("https://www.youtube.com/shorts/xyz", "youtube", "short", "xyz"),
    ("https://clips.twitch.tv/FunnyClipSlug", "twitch", "clip", "FunnyClipSlug"),
    ("https://www.twitch.tv/somestreamer/clip/Slug-1", "twitch", "clip", "Slug-1"),
    ("https://www.twitch.tv/videos/123456", "twitch", "vod", "123456"),
    ("https://www.twitch.tv/somestreamer", "twitch", "channel", "somestreamer"),
])
def test_classify(url, platform, obj, oid):
    c = classify_url(url)
    assert (c["platform"], c["object"], c["object_id"]) == (platform, obj, oid)


def test_class_e_makes_no_network_request(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    out = class_e_outcome("https://www.youtube.com/watch?v=abc123")
    assert out["acquired"] is False and out["network_requests_made"] == 0
    assert "does not download" in out["limitation"]
    assert "https://www.youtube.com/watch?v=abc123" in out["permission_request_draft"]
    assert out["rights_class"] == "E"


def test_cli_classify_exit_zero(capsys):
    from clipops.cli import main
    assert main(["source", "classify", "https://clips.twitch.tv/Abc"]) == 0
    assert "permission request draft" in capsys.readouterr().out
