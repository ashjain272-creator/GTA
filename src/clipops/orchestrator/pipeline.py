"""Stage orchestration with resumability (spec 1.3 P9, 5.4).

Each stage writes one artefact per source. A stage is skipped when its artefact
exists and its recorded input key (source hash + relevant config + code
version) matches; otherwise it reruns. Keys are stored inside each artefact.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import __version__
from ..analysis import audio as audio_mod
from ..analysis import audio_events as events_mod
from ..analysis import scenes as scenes_mod
from ..analysis import transcribe as asr_mod
from ..candidates.generate import generate
from ..config import data_path
from ..editing.plan import make_plan
from ..ingest import probe as probe_mod
from ..ingest import rights as rights_mod
from ..qa.checks import run_qa
from ..render.vertical import render
from ..runreport import RunReport, StageFailed
from ..storage.artefacts import read_json, source_dir, write_json


# Bump a stage's version whenever its implementation changes output, so cached
# artefacts are invalidated (resumability must never serve stale results).
STAGE_VERSIONS = {"probe": 1, "asr": 1, "audio": 1, "scenes": 1, "events": 1, "cands": 7}


def _key(*parts) -> str:
    return hashlib.sha256(json.dumps([__version__, *parts], sort_keys=True, default=str).encode()).hexdigest()[:16]


def _cached(path: Path, key: str) -> dict | None:
    if path.is_file():
        data = read_json(path)
        if data.get("_input_key") == key:
            return data
    return None


def _store(path: Path, key: str, data: dict) -> dict:
    data["_input_key"] = key
    write_json(path, data)
    return data


class Pipeline:
    def __init__(self, cfg: dict, report: RunReport):
        self.cfg, self.report = cfg, report
        self.repo = Path(cfg["_repo"])
        self.work = data_path(cfg, "work")
        self._memo: dict[tuple, dict] = {}

    # ------------------------------------------------------------ registration
    def add_source(self, path: Path, klass: str, *, game: str | None, grant: dict | None,
                   synthetic: bool = False, notes: str | None = None,
                   platform: str = "file", origin_url: str | None = None,
                   attestation: str | None = None) -> str:
        with self.report.stage("source_add") as st:
            rec = rights_mod.build_record(self.repo, path.resolve(), klass, game=game, grant=grant,
                                          synthetic=synthetic, notes=notes, platform=platform,
                                          origin_url=origin_url, attestation=attestation)
            d = source_dir(self.work, rec["source_id"])
            rights_mod.save_record(rec, d)
            st["source_id"] = rec["source_id"]
            if rec["monetisation_allowed"] != "yes":
                self.report.warn("source_add", "monetisation",
                                 f"monetisation_allowed={rec['monetisation_allowed']} (game policy / rights class)")
            return rec["source_id"]

    def add_url(self, url: str, klass: str, *, game: str | None, grant: dict | None,
                notes: str | None = None, attestation: str | None = None) -> list[str]:
        from ..ingest.acquire import acquire
        with self.report.stage("acquire") as st:
            got = acquire(url, klass, grant, self.cfg, data_path(self.cfg, "sources") / "url", attestation)
            st["items"] = len(got["items"])
            if got["items"][0]["provenance"]["platform"] == "youtube":
                self.report.warn("acquire", "tos_risk", got["items"][0]["provenance"]["basis"])
        ids = []
        for it in got["items"]:
            note = f"acquired: {it['provenance']}" + (f"; {notes}" if notes else "")
            ids.append(self.add_source(it["path"], klass, game=game, grant=grant, notes=note,
                                       platform=it["provenance"]["platform"], origin_url=it["provenance"]["url"],
                                       attestation=attestation))
        return ids

    def _src(self, source_id: str) -> tuple[Path, dict, Path]:
        d = self.work / source_id
        rec = rights_mod.gate(self.repo, d, self.cfg["rights"]["allowed_production_classes"])
        return d, rec, Path(rec["origin_path"])

    # ------------------------------------------------------------ stages
    def ingest(self, source_id: str) -> dict:
        if ("ingest", source_id) in self._memo:
            return self._memo[("ingest", source_id)]
        res = self._ingest(source_id)
        self._memo[("ingest", source_id)] = res
        return res

    def _ingest(self, source_id: str) -> dict:
        with self.report.stage("ingest") as st:
            d, rec, src = self._src(source_id)
            key = _key("probe", STAGE_VERSIONS["probe"], rec["sha256"])
            if (hit := _cached(d / "probe.json", key)):
                st["status"] = "cached"
                return hit
            from ..storage.artefacts import sha256_file
            if sha256_file(src) != rec["sha256"]:
                raise StageFailed("source_changed", "data", "source file hash differs from rights record")
            m = probe_mod.probe_source(src)
            for code, msg in probe_mod.probe_warnings(m):
                self.report.warn("ingest", code, msg)
            return _store(d / "probe.json", key, m)

    def analyse(self, source_id: str) -> dict:
        if ("analyse", source_id) in self._memo:
            return self._memo[("analyse", source_id)]
        res = self._analyse(source_id)
        self._memo[("analyse", source_id)] = res
        return res

    def _analyse(self, source_id: str) -> dict:
        d, rec, src = self._src(source_id)
        probe = self.ingest(source_id)
        out = {}
        has_audio = bool(probe["audio_streams"])
        with self.report.stage("transcribe") as st:
            key = _key("asr", STAGE_VERSIONS["asr"], rec["sha256"], self.cfg["asr"])
            if not has_audio:
                self.report.skip("transcribe", "no audio stream")
                st["status"] = "skipped"
                out["transcript"] = {"segments": []}
            elif (hit := _cached(d / "transcript.json", key)):
                st["status"] = "cached"
                out["transcript"] = hit
            else:
                t = asr_mod.transcribe(src, self.cfg)
                self.report.data["models"]["asr"] = f"{t['engine']}:{t['model']}:{t['compute_type']}"
                st["realtime_factor"] = t["timing"]["realtime_factor"]
                out["transcript"] = _store(d / "transcript.json", key, t)
        with self.report.stage("audio_analysis") as st:
            key = _key("audio", STAGE_VERSIONS["audio"], rec["sha256"], self.cfg["analysis"])
            if not has_audio:
                self.report.skip("audio_analysis", "no audio stream")
                st["status"] = "skipped"
                out["audio"] = {"curve": [], "summary": {"speechless_or_silent": True}}
            elif (hit := _cached(d / "audio.json", key)):
                st["status"] = "cached"
                out["audio"] = hit
            else:
                curve = audio_mod.loudness_curve(src)
                out["audio"] = _store(d / "audio.json", key, {"curve": curve, "summary": audio_mod.summarise(curve)})
        with self.report.stage("scene_detection") as st:
            key = _key("scenes", STAGE_VERSIONS["scenes"], rec["sha256"], self.cfg["analysis"])
            if (hit := _cached(d / "scenes.json", key)):
                st["status"] = "cached"
                out["scenes"] = hit
            else:
                cuts = scenes_mod.scene_cuts(src, self.cfg["analysis"]["scene_threshold"])
                out["scenes"] = _store(d / "scenes.json", key, {"cuts": cuts})
        with self.report.stage("audio_events") as st:
            key = _key("events", STAGE_VERSIONS["events"], rec["sha256"], self.cfg["models"]["yamnet"]["model_sha256"])
            if not has_audio:
                self.report.skip("audio_events", "no audio stream")
                st["status"] = "skipped"
                out["events"] = {"frames": [], "unscreened": False}
            elif (hit := _cached(d / "audio_events.json", key)):
                st["status"] = "cached"
                out["events"] = hit
            else:
                try:
                    ev = events_mod.tag(src, self.cfg)
                    self.report.data["models"]["audio_events"] = f"{ev['model']}:{ev['model_sha256'][:12]}"
                    out["events"] = _store(d / "audio_events.json", key, ev | {"unscreened": False})
                except StageFailed as e:
                    # fail closed: candidates from an unscreened source cannot pass the music gate
                    st["status"] = "failed_unscreened"
                    st["error"] = {"code": e.code, "message": e.message}
                    self.report.warn("audio_events", "unscreened", f"music screen unavailable ({e.code}); candidates will be rejected")
                    out["events"] = {"frames": [], "unscreened": True, "error": e.message}
        return out

    def candidates(self, source_id: str) -> dict:
        if ("candidates", source_id) in self._memo:
            return self._memo[("candidates", source_id)]
        res = self._candidates(source_id)
        self._memo[("candidates", source_id)] = res
        return res

    def _candidates(self, source_id: str) -> dict:
        d, rec, _ = self._src(source_id)
        probe = self.ingest(source_id)
        a = self.analyse(source_id)
        with self.report.stage("candidates") as st:
            # limitation is reported on every run, cached or not (spec 2.7: no silent degradation)
            from ..candidates.generate import MODEL_VERSION
            self.report.warn("candidates", "heuristic_ranker",
                             f"ranking uses {MODEL_VERSION}: unvalidated, uncertainty reported high")
            key = _key("cands", STAGE_VERSIONS["cands"], a["transcript"].get("_input_key"), a["audio"].get("_input_key"),
                       a["scenes"].get("_input_key"), a["events"].get("_input_key"), a["events"].get("unscreened"),
                       self.cfg["candidates"], self.cfg["analysis"], rec["class"], rec.get("grant"))
            if (hit := _cached(d / "candidates.json", key)):
                st["status"] = "cached"
                return hit
            res = generate(source_id, probe["duration_us"], a["transcript"], [tuple(x) for x in a["audio"]["curve"]],
                           a["scenes"]["cuts"], a["audio"]["summary"], rec, self.cfg, events=a["events"])
            st.update(res["counts"])
            return _store(d / "candidates.json", key, res)

    def plan(self, source_id: str, candidate_id: str | None = None, style: str | None = None,
             use_history: bool = True) -> dict:
        from ..editing import framing as framing_mod
        from ..editing import styles as styles_mod
        d, rec, src = self._src(source_id)
        cands = self.candidates(source_id)
        probe = self.ingest(source_id)
        events = self.analyse(source_id)["events"]
        with self.report.stage("plan") as st:
            pool = [c for c in cands["candidates"] if c["status"] == "proposed"]
            if candidate_id:
                pool = [c for c in pool if c["candidate_id"] == candidate_id]
            if not pool:
                raise StageFailed("no_viable_candidate", "data",
                                  "no proposed candidate: publishing nothing is the correct outcome (spec 7.8)")
            cand = pool[0]
            transcript = read_json(d / "transcript.json") if (d / "transcript.json").is_file() else {"segments": []}
            prof = styles_mod.moment_profile(cand, events)
            from ..qa.window_checks import black_edges, source_flash_risk
            bb = cand["boundaries"]
            flash = source_flash_risk(src, bb["start_us"] / 1e6, (bb["end_us"] - bb["start_us"]) / 1e6, self.cfg)
            black = black_edges(src, bb["start_us"], bb["end_us"])
            sel = styles_mod.select_style(self.repo, self.cfg, prof, force=style, flash_risk=flash["risk"],
                                          recent=None if use_history else [])
            b = cand["boundaries"]
            v = probe["video"]
            camera = None
            for gp in rec.get("game_policies") or []:
                ref = gp.get("policy_ref") or ""
                if ref.startswith("config/game_policies.yaml#"):
                    import yaml as _yaml
                    reg = _yaml.safe_load((self.repo / "config" / "game_policies.yaml").read_text())
                    camera = (reg.get(ref.split("#", 1)[1]) or {}).get("camera")
            fr = framing_mod.track(src, b["start_us"] / 1e6, (b["end_us"] - b["start_us"]) / 1e6,
                                   v["width"], v["height"], self.cfg, camera=camera,
                                   cut_times_s=[c["time_us"] / 1e6 for c in self.analyse(source_id)["scenes"]["cuts"]])
            # keyframes are relative to the window start, which is also the render input start
            game = (rec.get("game_policies") or [{}])[0].get("game")
            p = make_plan(cand, transcript, self.cfg, style_sel=sel, framing=fr, game=game,
                          music_covered=bool((rec.get("grant") or {}).get("covers_audio")),
                          flash_mitigation=flash["mitigation"], black_trim=black)
            if flash["risk"]:
                self.report.warn("plan", "flash_mitigation", f"source window flashes {flash['max_flashes_per_s']}/s: "
                                 f"photosensitivity filter applied {flash['mitigation']}")
            st.update(plan_id=p["plan_id"], style=sel["name"], layout=fr["layout"],
                      zooms=len(p["zooms"]), sfx=len(p["sfx"]), structure=p["structure"]["name"])
            if fr["layout"] == "blur_fill":
                self.report.warn("plan", "framing_fallback", f"blur_fill used: {fr['reason']}")
            if not style and use_history:
                styles_mod.record_choice(self.cfg, sel["name"])
            write_json(d / "plans" / f"{p['plan_id']}.json", p)
            return p

    def render_and_qa(self, source_id: str, plan: dict) -> tuple[dict, dict]:
        """Render, inspect, and repair what can be repaired automatically (spec 10.5 repair loop)."""
        d, _, src = self._src(source_id)
        v = self.ingest(source_id)["video"]
        ladder = self.cfg["flash_mitigation"]["ladder"]
        repairs = []
        for attempt in range(len(ladder) + 1):
            with self.report.stage("render") as st:
                info = render(plan, src, data_path(self.cfg, "renders") / source_id, self.cfg, v["width"], v["height"])
                st["short_id"] = info["short_id"]
                write_json(d / "renders" / f"{info['short_id']}.json", info)
            with self.report.stage("qa") as st:
                qa = run_qa(info, plan, self.cfg, d / "qa")
                st["passed"], st["failed"] = qa["passed"], qa["failed"]
            if "photosensitive_flash" in qa["failed"]:
                cur = plan.get("flash_mitigation") or {}
                nxt = next(([f, t] for f, t in ladder if not cur or t < cur.get("threshold", 9)), None)
                if nxt:
                    plan["flash_mitigation"] = {"frames": nxt[0], "threshold": nxt[1]}
                    repairs.append({"failed": "photosensitive_flash", "action": f"photosensitivity f={nxt[0]} t={nxt[1]}"})
                    self.report.warn("qa", "repair", repairs[-1]["action"])
                    continue
            break
        qa["repairs"] = repairs
        plan["qa_repairs"] = repairs
        write_json(d / "qa" / f"{info['short_id']}.json", qa)
        write_json(d / "plans" / f"{plan['plan_id']}.json", plan)
        self.report.artefact("render", Path(info["path"]))
        if not qa["passed"]:
            self.report.data["stages"][-1]["status"] = "failed_checks"
        self.report.data["qa_summary"] = {"short_id": qa["short_id"], "passed": qa["passed"],
                                          "failed": qa["failed"], "review_flags": qa["review_flags"],
                                          "publishable": qa["publishable"], "repairs": repairs}
        for flag in qa["review_flags"]:
            self.report.operator_action(f"Review {qa['short_id']}: {flag}")
        self.report.artefact("contact_sheet", Path(qa["contact_sheet"]))
        return info, qa
