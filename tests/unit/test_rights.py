"""Rights gate (spec 4.3, 4.15): fails closed."""
from __future__ import annotations

from pathlib import Path

import pytest

from clipops.ingest import rights

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def media(tmp_path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"not really media but hashable")
    return p


@pytest.mark.parametrize("klass", ["E", "F"])
def test_class_e_and_f_are_refused_at_registration(media, klass):
    with pytest.raises(rights.RightsRefused, match=f"class {klass}"):
        rights.build_record(REPO, media, klass)


def test_missing_record_fails_closed(tmp_path):
    with pytest.raises(rights.RightsRefused, match="no rights record"):
        rights.gate(REPO, tmp_path, ["A", "B", "C"])


def test_tampered_record_class_e_is_refused_by_gate(media, tmp_path):
    rec = rights.build_record(REPO, media, "A")
    rec["class"] = "E"
    rights.save_record(rec, tmp_path)
    with pytest.raises(rights.RightsRefused, match="class E"):
        rights.gate(REPO, tmp_path, ["A", "B", "C"])


def test_class_b_requires_grant(media):
    import jsonschema
    with pytest.raises(jsonschema.ValidationError):
        rights.build_record(REPO, media, "B")
    rec = rights.build_record(REPO, media, "B", grant={"document_ref": "grants/x.pdf", "scope": {"platforms": ["youtube"]}})
    assert rec["class"] == "B"


def test_expired_grant_is_refused(media, tmp_path):
    rec = rights.build_record(REPO, media, "B", grant={"document_ref": "g", "scope": {}, "expires": "2000-01-01"})
    rights.save_record(rec, tmp_path)
    with pytest.raises(rights.RightsRefused, match="expired"):
        rights.gate(REPO, tmp_path, ["A", "B", "C"])


def test_class_not_in_allowed_list_is_refused(media, tmp_path):
    rights.save_record(rights.build_record(REPO, media, "A"), tmp_path)
    with pytest.raises(rights.RightsRefused):
        rights.gate(REPO, tmp_path, ["B"])


def test_rockstar_title_disables_monetisation(media):
    rec = rights.build_record(REPO, media, "A", game="Grand Theft Auto V")
    assert rec["monetisation_allowed"] == "no"
    assert rec["game_policies"][0]["risk"] == "high"
    assert rec["game_policies"][0]["policy_ref"].endswith("#rockstar")


def test_unknown_game_is_high_risk_and_unknown_monetisation(media):
    rec = rights.build_record(REPO, media, "A", game="Some Unlisted Game")
    assert rec["game_policies"][0]["policy_checked"] == "never"
    assert rec["monetisation_allowed"] == "unknown"
