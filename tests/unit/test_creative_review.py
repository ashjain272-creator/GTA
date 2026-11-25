from clipops.qa.creative import review


def _plan(**k):
    words = [{"text": "Watch", "start_us": 500_000, "end_us": 800_000, "verified": True},
             {"text": "this!", "start_us": 900_000, "end_us": 1_200_000, "verified": True}]
    base = {"duration_us": 15_000_000, "structure": {"name": "cold_open"}, "hook": {"text": "x", "source": "verbatim transcript quote"},
            "subtitles": {"cues": [{"words": words}]}, "framing": {"layout": "tracked_crop", "concentration": 0.8, "reason": "m"},
            "contribution": [1, 2, 3], "freeze_end_us": 400_000}
    return base | k


QA = {"checks": [{"name": "integrated_loudness", "passed": True, "measured": -14.2},
                 {"name": "true_peak", "passed": True, "measured": -1.8},
                 {"name": "subtitle_reading_speed", "passed": True, "measured": 15},
                 {"name": "subtitle_safe_area", "passed": True, "measured": {}}]}


def test_scores_are_bounded_and_explained():
    r = review(_plan(), QA, {"signals": {"impact_score": 0.6, "reaction": 1.0}})
    assert all(1 <= v["score"] <= 5 and v["evidence"] for v in r["scores"].values())
    assert r["verdict"] == "strong"


def test_weak_edit_is_called_weak_with_reasons():
    p = _plan(structure={"name": "linear_build"}, hook={"text": "", "source": "none"}, contribution=[],
              subtitles={"cues": []}, freeze_end_us=0, framing={"layout": "blur_fill", "reason": "spread"})
    r = review(p, {"checks": []}, {"signals": {"impact_score": 0.0, "reaction": 0.0}})
    assert r["verdict"] == "weak" and r["weaknesses"]
