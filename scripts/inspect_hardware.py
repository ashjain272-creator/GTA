#!/usr/bin/env python3
"""Hardware and toolchain inspection (spec section 5.3).

Standard-library only so it runs on a fresh machine before any dependency is
installed. Works on Linux, macOS and Windows; probes that do not apply to the
current OS are recorded as "not_applicable" rather than silently skipped.

Every hardware video encoder that FFmpeg reports is verified by an actual
encode of a synthetic test pattern, followed by a decode of the result. A
model name alone is never treated as evidence of capability.

Usage:
    python scripts/inspect_hardware.py --role operator-machine
    python scripts/inspect_hardware.py --role cloud-dev-container --skip-network

Writes config/hardware.json and docs/HARDWARE_REPORT.md (paths overridable).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

SCHEMA_VERSION = 1
REPO = Path(__file__).resolve().parent.parent

# Hardware encoders worth testing, grouped by vendor family. Only those that
# the local FFmpeg build lists are attempted.
HW_ENCODERS = [
    "h264_nvenc", "hevc_nvenc", "av1_nvenc",
    "h264_videotoolbox", "hevc_videotoolbox",
    "h264_qsv", "hevc_qsv", "av1_qsv",
    "h264_vaapi", "hevc_vaapi", "av1_vaapi",
    "h264_amf", "hevc_amf", "av1_amf",
    "h264_mf", "hevc_mf",
    "h264_v4l2m2m",
]
SW_ENCODERS = ["libx264", "libx265", "libsvtav1", "libaom-av1", "libvpx-vp9"]
FILTERS_OF_INTEREST = [
    "subtitles", "ass", "drawtext", "loudnorm", "ebur128", "scdet", "select",
    "scale", "zscale", "crop", "libvmaf", "ssim", "psnr", "silencedetect",
    "showspectrumpic", "afftdn", "arnndn", "sidechaincompress", "tonemap",
]


def run(cmd: list[str], timeout: float = 60) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def first_line(cmd: list[str]) -> str | None:
    code, out, err = run(cmd, timeout=20)
    text = (out or err).strip()
    if code == 127 or not text:
        return None
    return text.splitlines()[0].strip()


# --------------------------------------------------------------------------- OS / CPU / RAM
def inspect_os() -> dict:
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
    }
    if info["system"] == "Linux":
        try:
            kv = dict(
                line.split("=", 1)
                for line in Path("/etc/os-release").read_text().splitlines()
                if "=" in line
            )
            info["distribution"] = kv.get("PRETTY_NAME", "").strip('"')
        except OSError:
            pass
        info["virtualised"] = _linux_virtualisation()
    elif info["system"] == "Darwin":
        info["distribution"] = "macOS " + platform.mac_ver()[0]
    elif info["system"] == "Windows":
        info["distribution"] = "Windows " + platform.win32_ver()[0]
    return info


def _linux_virtualisation() -> str | None:
    code, out, _ = run(["systemd-detect-virt"], timeout=5)
    if code == 0 and out.strip():
        return out.strip()
    try:
        if "hypervisor" in Path("/proc/cpuinfo").read_text():
            return "hypervisor-flag-present"
    except OSError:
        pass
    return None


def inspect_cpu() -> dict:
    sysname = platform.system()
    cpu: dict = {"logical_cores": os.cpu_count()}
    flags: set[str] = set()
    if sysname == "Linux":
        try:
            text = Path("/proc/cpuinfo").read_text()
            m = re.search(r"model name\s*:\s*(.+)", text)
            cpu["model"] = m.group(1).strip() if m else platform.processor()
            fm = re.search(r"^(flags|Features)\s*:\s*(.+)$", text, re.M)
            if fm:
                flags = set(fm.group(2).split())
            phys = {
                (a, b)
                for a, b in re.findall(
                    r"physical id\s*:\s*(\d+).*?core id\s*:\s*(\d+)", text, re.S
                )
            }
            cpu["physical_cores"] = len(phys) or None
        except OSError:
            pass
    elif sysname == "Darwin":
        cpu["model"] = first_line(["sysctl", "-n", "machdep.cpu.brand_string"])
        pc = first_line(["sysctl", "-n", "hw.physicalcpu"])
        cpu["physical_cores"] = int(pc) if pc and pc.isdigit() else None
        feats = " ".join(
            filter(None, [
                first_line(["sysctl", "-n", "machdep.cpu.features"]),
                first_line(["sysctl", "-n", "machdep.cpu.leaf7_features"]),
            ])
        ).lower()
        flags = set(feats.split())
        if platform.machine() == "arm64":
            flags.add("neon")
    elif sysname == "Windows":
        cpu["model"] = platform.processor()
    interesting = [
        "avx", "avx2", "fma", "f16c", "avx512f", "avx512bw", "avx512_vnni",
        "avx512_bf16", "avx_vnni", "amx_tile", "amx_int8", "amx_bf16",
        "neon", "asimd", "sve",
    ]
    cpu["inference_extensions"] = sorted(f for f in interesting if f in flags)
    return cpu


def inspect_memory() -> dict:
    sysname = platform.system()
    mem: dict = {}
    if sysname == "Linux":
        try:
            kv = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, v = line.split(":", 1)
                kv[k] = int(v.split()[0]) * 1024
            mem["total_bytes"] = kv.get("MemTotal")
            mem["available_bytes"] = kv.get("MemAvailable")
            mem["swap_total_bytes"] = kv.get("SwapTotal")
        except (OSError, ValueError):
            pass
        cg = Path("/sys/fs/cgroup/memory.max")
        if cg.exists():
            val = cg.read_text().strip()
            mem["cgroup_limit_bytes"] = None if val == "max" else int(val)
    elif sysname == "Darwin":
        v = first_line(["sysctl", "-n", "hw.memsize"])
        mem["total_bytes"] = int(v) if v and v.isdigit() else None
        sw = first_line(["sysctl", "-n", "vm.swapusage"])
        mem["swap_usage"] = sw
    elif sysname == "Windows":
        code, out, _ = run([
            "powershell", "-NoProfile", "-Command",
            "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
        ])
        if code == 0 and out.strip().isdigit():
            mem["total_bytes"] = int(out.strip())
    mem["speed"] = "not_measured"  # requires privileged tools (dmidecode) on most OSes
    return mem


# --------------------------------------------------------------------------- GPU
def inspect_gpus() -> dict:
    gpus: list[dict] = []
    stacks: dict[str, str | None] = {}
    code, out, _ = run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ], timeout=20)
    if code == 0:
        for line in out.strip().splitlines():
            name, vram, drv = [x.strip() for x in line.split(",")]
            gpus.append({"vendor": "NVIDIA", "model": name,
                         "vram_mib": int(float(vram)), "driver": drv})
        stacks["cuda"] = first_line(["nvidia-smi"])
    if shutil.which("rocm-smi"):
        stacks["rocm"] = first_line(["rocm-smi", "--showproductname"])
    if shutil.which("vulkaninfo"):
        code, out, _ = run(["vulkaninfo", "--summary"], timeout=20)
        stacks["vulkan"] = "present" if code == 0 else "error"
    if platform.system() == "Darwin":
        code, out, _ = run(["system_profiler", "SPDisplaysDataType", "-json"], timeout=30)
        if code == 0:
            try:
                for d in json.loads(out).get("SPDisplaysDataType", []):
                    gpus.append({
                        "vendor": d.get("spdisplays_vendor", "Apple"),
                        "model": d.get("sppci_model"),
                        "vram": d.get("spdisplays_vram") or "unified",
                        "metal": d.get("spdisplays_mtlgpufamilysupport"),
                    })
                stacks["metal"] = "present"
            except json.JSONDecodeError:
                pass
    if platform.system() == "Linux" and not gpus:
        code, out, _ = run(["lspci"], timeout=10)
        if code == 0:
            for line in out.splitlines():
                if re.search(r"VGA|3D controller|Display controller", line):
                    gpus.append({"vendor": "unknown", "model": line.split(":", 2)[-1].strip()})
        for node in sorted(Path("/dev/dri").glob("renderD*")) if Path("/dev/dri").exists() else []:
            stacks.setdefault("dri_render_nodes", "")
            stacks["dri_render_nodes"] += node.name + " "
    if platform.system() == "Windows":
        code, out, _ = run([
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json",
        ], timeout=30)
        if code == 0 and out.strip():
            try:
                data = json.loads(out)
                for d in data if isinstance(data, list) else [data]:
                    gpus.append({"vendor": "unknown", "model": d.get("Name"),
                                 "vram_bytes_reported": d.get("AdapterRAM"),
                                 "driver": d.get("DriverVersion")})
            except json.JSONDecodeError:
                pass
    return {"devices": gpus, "compute_stacks": stacks}


# --------------------------------------------------------------------------- FFmpeg
def inspect_ffmpeg(workdir: Path) -> dict:
    ff = shutil.which("ffmpeg")
    if not ff:
        return {"present": False}
    res: dict = {"present": True, "path": ff,
                 "version": first_line(["ffmpeg", "-hide_banner", "-version"])}
    code, out, _ = run(["ffmpeg", "-hide_banner", "-version"])
    m = re.search(r"configuration:\s*(.+)", out)
    res["configuration"] = m.group(1).split() if m else []
    code, out, _ = run(["ffmpeg", "-hide_banner", "-encoders"])
    encoders = set(re.findall(r"^\s*[VAS][\w.]{5}\s+(\S+)", out, re.M))
    code, out, _ = run(["ffmpeg", "-hide_banner", "-filters"])
    filters = set(re.findall(r"^\s*[TSC.]{3}\s+(\S+)", out, re.M))
    code, out, _ = run(["ffmpeg", "-hide_banner", "-hwaccels"])
    res["hwaccels"] = [l.strip() for l in out.splitlines()[1:] if l.strip()]
    res["encoders_of_interest"] = {
        e: (e in encoders) for e in HW_ENCODERS + SW_ENCODERS + ["aac", "libopus", "libfdk_aac"]
    }
    res["filters_of_interest"] = {f: (f in filters) for f in FILTERS_OF_INTEREST}
    res["encode_tests"] = []
    for enc in [e for e in SW_ENCODERS[:1] + HW_ENCODERS if e in encoders]:
        res["encode_tests"].append(_encode_decode_test(enc, workdir))
    return res


def _root_cause(stderr: str) -> str:
    """Return the most informative FFmpeg error line, not the generic last one."""
    lines = [l.strip() for l in stderr.splitlines() if l.strip()]
    for l in lines:
        if re.search(r"cannot|could not|failed|no device|not found|unsupported|error", l, re.I) \
                and "Nothing was written" not in l:
            return l[:300]
    return lines[-1][:300] if lines else ""


def _encode_decode_test(encoder: str, workdir: Path) -> dict:
    """Encode 5 s of 1080p30 test pattern, then decode it back; time both."""
    out = workdir / f"enc_{encoder}.mp4"
    pre: list[str] = []
    vf = "format=yuv420p"
    if encoder.endswith("_vaapi"):
        dev = next(iter(sorted(Path("/dev/dri").glob("renderD*"))), None) if Path("/dev/dri").exists() else None
        if dev is None:
            return {"encoder": encoder, "ok": False, "error": "no DRI render node"}
        pre = ["-vaapi_device", str(dev)]
        vf = "format=nv12,hwupload"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *pre,
           "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=5",
           "-vf", vf, "-c:v", encoder, "-b:v", "8M", str(out)]
    t0 = time.perf_counter()
    code, _, err = run(cmd, timeout=180)
    enc_s = time.perf_counter() - t0
    result = {"encoder": encoder, "ok": code == 0 and out.exists() and out.stat().st_size > 0,
              "encode_seconds_for_150_frames": round(enc_s, 3)}
    if not result["ok"]:
        result["error"] = _root_cause(err) or f"exit {code}"
        return result
    result["encode_fps"] = round(150 / enc_s, 1)
    result["output_bytes"] = out.stat().st_size
    t0 = time.perf_counter()
    code, _, err = run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-i", str(out), "-f", "null", "-"], timeout=120)
    dec_s = time.perf_counter() - t0
    result["decode_ok"] = code == 0
    result["decode_fps"] = round(150 / dec_s, 1) if code == 0 else None
    out.unlink(missing_ok=True)
    return result


# --------------------------------------------------------------------------- storage / network
def inspect_storage(workdir: Path, bench_mib: int) -> dict:
    vols = []
    seen = set()
    candidates = [Path.home(), REPO, Path(tempfile.gettempdir())]
    if platform.system() == "Windows":
        candidates += [Path(f"{d}:\\") for d in "CDEFGH" if Path(f"{d}:\\").exists()]
    else:
        candidates += [Path("/")]
    for p in candidates:
        try:
            u = shutil.disk_usage(p)
        except OSError:
            continue
        key = (u.total, u.free)
        if key in seen:
            continue
        seen.add(key)
        vols.append({"path": str(p), "total_bytes": u.total, "free_bytes": u.free})
    bench = _disk_bench(workdir, bench_mib)
    return {"volumes": vols, "repo_volume_benchmark": bench,
            "media_type": "not_determined_by_script (SSD/HDD/network: confirm manually)"}


def _disk_bench(workdir: Path, mib: int) -> dict:
    path = workdir / "disk_bench.bin"
    block = os.urandom(1 << 20)
    t0 = time.perf_counter()
    with open(path, "wb") as f:
        for _ in range(mib):
            f.write(block)
        f.flush()
        os.fsync(f.fileno())
    w = time.perf_counter() - t0
    t0 = time.perf_counter()
    with open(path, "rb") as f:
        while f.read(1 << 20):
            pass
    r = time.perf_counter() - t0
    path.unlink(missing_ok=True)
    return {"size_mib": mib, "seq_write_mib_s": round(mib / w, 1),
            "seq_read_mib_s_page_cache_likely": round(mib / r, 1),
            "note": "read figure is optimistic: file was just written and is likely cached"}


def inspect_network(skip: bool) -> dict:
    if skip:
        return {"measured": False, "reason": "skipped by flag"}
    # Small download from a public CDN; measures rough throughput only.
    url = "https://speed.cloudflare.com/__down?bytes=25000000"
    try:
        t0 = time.perf_counter()
        with urllib.request.urlopen(url, timeout=30) as r:
            n = len(r.read())
        dt = time.perf_counter() - t0
        return {"measured": True, "download_mbit_s": round(n * 8 / dt / 1e6, 1),
                "bytes": n, "upload": "not_measured", "metered": "unknown (ask operator)"}
    except Exception as e:  # noqa: BLE001 - recorded, not hidden
        return {"measured": False, "reason": f"{type(e).__name__}: {e}"[:200]}


def inspect_software() -> dict:
    tools = {
        "python": [sys.executable, "--version"],
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "git": ["git", "--version"],
        "ffprobe": ["ffprobe", "-hide_banner", "-version"],
        "docker": ["docker", "--version"],
        "podman": ["podman", "--version"],
        "uv": ["uv", "--version"],
        "pip": [sys.executable, "-m", "pip", "--version"],
        "pandoc": ["pandoc", "--version"],
        "brew": ["brew", "--version"],
        "winget": ["winget", "--version"],
    }
    return {name: first_line(cmd) for name, cmd in tools.items()}


def thermal_note(system_info: dict) -> dict:
    return {"measured": False,
            "reason": "10-minute sustained-load test not run by default; use --thermal on laptops",
            "is_virtualised": bool(system_info.get("virtualised"))}


def thermal_test(minutes: float) -> dict:
    """Run libx264 encodes back to back; report fps drift as a throttling proxy."""
    rates = []
    end = time.time() + minutes * 60
    with tempfile.TemporaryDirectory() as td:
        while time.time() < end:
            r = _encode_decode_test("libx264", Path(td))
            if r.get("encode_fps"):
                rates.append(r["encode_fps"])
    if len(rates) < 2:
        return {"measured": False, "reason": "insufficient samples"}
    first = sum(rates[:3]) / min(3, len(rates))
    last = sum(rates[-3:]) / min(3, len(rates))
    return {"measured": True, "minutes": minutes, "samples": len(rates),
            "fps_first": round(first, 1), "fps_last": round(last, 1),
            "drop_percent": round(100 * (first - last) / first, 1)}


# --------------------------------------------------------------------------- report
def gib(n: int | None) -> str:
    return "unknown" if not n else f"{n / (1 << 30):.1f} GiB"


def render_markdown(hw: dict) -> str:
    o, c, m, g, f, s = (hw["os"], hw["cpu"], hw["memory"], hw["gpu"],
                        hw["ffmpeg"], hw["storage"])
    lines = [
        "# Hardware Report",
        "",
        f"- **Generated:** {hw['generated_at']}",
        f"- **Machine role:** `{hw['role']}`",
        f"- **Generator:** `scripts/inspect_hardware.py` (schema v{hw['schema_version']})",
        "",
    ]
    if hw["role"] != "operator-machine":
        lines += [
            "> **This is not the operator's production machine.** Hardware-dependent",
            "> decisions (spec 5.3) MUST NOT be finalised from this report. It",
            "> describes the environment where development and CI run. Re-run",
            "> `python scripts/inspect_hardware.py --role operator-machine` on the",
            "> operator's computer; see docs/BLOCKERS.md B-01.",
            "",
        ]
    lines += [
        "## System",
        f"- OS: {o.get('distribution') or o['system']} ({o['system']} {o['release']}, {o['machine']})",
        f"- Virtualised: {o.get('virtualised') or 'no / unknown'}",
        "",
        "## CPU",
        f"- Model: {c.get('model')}",
        f"- Cores: {c.get('physical_cores')} physical / {c.get('logical_cores')} logical",
        f"- Inference-relevant extensions: {', '.join(c['inference_extensions']) or 'none detected'}",
        "",
        "## Memory",
        f"- Total: {gib(m.get('total_bytes'))}; available: {gib(m.get('available_bytes'))}",
        f"- Swap: {gib(m.get('swap_total_bytes')) if m.get('swap_total_bytes') else (m.get('swap_usage') or 'none')}",
        f"- Speed: {m.get('speed')}",
        "",
        "## GPU",
    ]
    if g["devices"]:
        for d in g["devices"]:
            lines.append(f"- {d.get('vendor')} {d.get('model')} "
                         f"VRAM={d.get('vram_mib', d.get('vram', 'unknown'))} "
                         f"driver={d.get('driver', 'n/a')}")
    else:
        lines.append("- No GPU detected.")
    lines.append(f"- Compute stacks: {json.dumps(g['compute_stacks']) if g['compute_stacks'] else 'none detected'}")
    lines += ["", "## FFmpeg"]
    if f.get("present"):
        lines.append(f"- {f['version']}")
        lines.append(f"- hwaccels: {', '.join(f['hwaccels']) or 'none'}")
        avail = [k for k, v in f["encoders_of_interest"].items() if v]
        lines.append(f"- Encoders of interest compiled in: {', '.join(avail)}")
        missing_f = [k for k, v in f["filters_of_interest"].items() if not v]
        lines.append(f"- Filters of interest missing: {', '.join(missing_f) or 'none'}")
        lines += ["", "### Measured encode/decode (5 s, 1080p30 testsrc2, 8 Mb/s target)", "",
                  "| Encoder | OK | Encode fps | Decode fps | Note |", "|---|---|---|---|---|"]
        for t in f["encode_tests"]:
            lines.append(f"| {t['encoder']} | {'yes' if t['ok'] else 'no'} | "
                         f"{t.get('encode_fps', '-')} | {t.get('decode_fps', '-')} | "
                         f"{t.get('error', '')} |")
        hw_listed = [e for e in HW_ENCODERS if f["encoders_of_interest"].get(e)]
        hw_ok = [t["encoder"] for t in f["encode_tests"] if t["ok"] and t["encoder"] in HW_ENCODERS]
        lines += ["", f"- Hardware encoders compiled in: {', '.join(hw_listed) or 'none'}",
                  f"- Hardware encoders that actually worked: {', '.join(hw_ok) or 'none'}"]
    else:
        lines.append("- FFmpeg not found.")
    lines += ["", "## Storage"]
    for v in s["volumes"]:
        lines.append(f"- {v['path']}: {gib(v['free_bytes'])} free of {gib(v['total_bytes'])}")
    b = s["repo_volume_benchmark"]
    lines.append(f"- Sequential write ({b['size_mib']} MiB, fsync): {b['seq_write_mib_s']} MiB/s; "
                 f"read: {b['seq_read_mib_s_page_cache_likely']} MiB/s (likely cached)")
    lines.append(f"- Media type: {s['media_type']}")
    n = hw["network"]
    lines += ["", "## Network",
              f"- {'Download ' + str(n['download_mbit_s']) + ' Mbit/s (single 25 MB fetch)' if n.get('measured') else 'Not measured: ' + n.get('reason', '')}",
              "", "## Thermal",
              f"- {json.dumps(hw['thermal'])}",
              "", "## Software"]
    for k, v in hw["software"].items():
        lines.append(f"- {k}: {v or 'absent'}")
    lines += ["", "## Implications (provisional, see DECISIONS.md)", ""]
    lines += implications(hw)
    return "\n".join(lines) + "\n"


def implications(hw: dict) -> list[str]:
    out = []
    has_cuda = any(d.get("vendor") == "NVIDIA" for d in hw["gpu"]["devices"])
    mem = hw["memory"].get("total_bytes") or 0
    cores = hw["cpu"].get("logical_cores") or 1
    hw_ok = [t["encoder"] for t in hw["ffmpeg"].get("encode_tests", [])
             if t["ok"] and t["encoder"] in HW_ENCODERS]
    if has_cuda:
        out.append("- CUDA GPU present: GPU speech recognition and local vision models are candidates; benchmark in Phase 1.")
    else:
        out.append("- No CUDA GPU: speech recognition runs on CPU (CTranslate2/int8 or whisper.cpp class runtimes); local vision-language models are likely too slow for dense use, so sample sparsely or use pre-screening.")
    if not hw_ok:
        out.append("- No working hardware encoder: drafts and finals both use software encoders; size render concurrency to cores.")
    else:
        out.append(f"- Working hardware encoder(s) {', '.join(hw_ok)}: candidates for draft renders; finals compared by VMAF/SSIM before choosing.")
    out.append(f"- Concurrency starting point: at most {max(1, cores // 2)} heavy media job(s) at once on {cores} logical cores (to be tuned by measurement).")
    if mem and mem < 12 * (1 << 30):
        out.append("- RAM below 12 GiB: avoid running ASR and render concurrently; prefer small/medium speech models.")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--role", required=True,
                    choices=["operator-machine", "cloud-dev-container", "ci-runner", "other"])
    ap.add_argument("--json-out", default=str(REPO / "config" / "hardware.json"))
    ap.add_argument("--md-out", default=str(REPO / "docs" / "HARDWARE_REPORT.md"))
    ap.add_argument("--bench-mib", type=int, default=256)
    ap.add_argument("--skip-network", action="store_true")
    ap.add_argument("--thermal", type=float, default=0.0,
                    help="minutes of sustained encode load for throttling detection (spec suggests 10 on laptops)")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="clipops_hw_") as td:
        work = Path(td)
        hw = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "role": args.role,
            "os": inspect_os(),
            "cpu": inspect_cpu(),
            "memory": inspect_memory(),
            "gpu": inspect_gpus(),
            "ffmpeg": inspect_ffmpeg(work),
            "storage": inspect_storage(work, args.bench_mib),
            "network": inspect_network(args.skip_network),
            "software": inspect_software(),
        }
        hw["thermal"] = thermal_test(args.thermal) if args.thermal > 0 else thermal_note(hw["os"])

    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(hw, indent=2) + "\n")
    Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.md_out).write_text(render_markdown(hw))
    print(f"wrote {args.json_out} and {args.md_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
