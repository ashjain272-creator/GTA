# Hardware Report

- **Generated:** 2026-11-21T21:06:21+00:00
- **Machine role:** `cloud-dev-container`
- **Generator:** `scripts/inspect_hardware.py` (schema v1)

> **This is not the operator's production machine.** Hardware-dependent
> decisions (spec 5.3) MUST NOT be finalised from this report. It
> describes the environment where development and CI run. Re-run
> `python scripts/inspect_hardware.py --role operator-machine` on the
> operator's computer; see docs/BLOCKERS.md B-01.

## System
- OS: Ubuntu 24.04.5 LTS (Linux 6.18.44-fc-v726, x86_64)
- Virtualised: docker

## CPU
- Model: Intel(R) Xeon(R) Processor @ 2.10GHz
- Cores: 4 physical / 4 logical
- Inference-relevant extensions: amx_bf16, amx_int8, amx_tile, avx, avx2, avx512_bf16, avx512_vnni, avx512bw, avx512f, avx_vnni, f16c, fma

## Memory
- Total: 15.7 GiB; available: 15.2 GiB
- Swap: none
- Speed: not_measured

## GPU
- No GPU detected.
- Compute stacks: none detected

## FFmpeg
- ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
- hwaccels: vdpau, cuda, vaapi, qsv, drm, opencl, vulkan
- Encoders of interest compiled in: h264_nvenc, hevc_nvenc, av1_nvenc, h264_qsv, hevc_qsv, av1_qsv, h264_vaapi, hevc_vaapi, av1_vaapi, h264_v4l2m2m, libx264, libx265, libsvtav1, libaom-av1, libvpx-vp9, aac, libopus
- Filters of interest missing: libvmaf

### Measured encode/decode (5 s, 1080p30 testsrc2, 8 Mb/s target)

| Encoder | OK | Encode fps | Decode fps | Note |
|---|---|---|---|---|
| libx264 | yes | 54.6 | 353.4 |  |
| h264_nvenc | no | - | - | [h264_nvenc @ 0x56446baddbc0] Cannot load libcuda.so.1 |
| hevc_nvenc | no | - | - | [hevc_nvenc @ 0x55974a08fbc0] Cannot load libcuda.so.1 |
| av1_nvenc | no | - | - | [av1_nvenc @ 0x561bd92b5bc0] Cannot load libcuda.so.1 |
| h264_qsv | no | - | - | [h264_qsv @ 0x55a4cf21dbc0] Error creating a MFX session: -9. |
| hevc_qsv | no | - | - | [hevc_qsv @ 0x55ad99aa9bc0] Error creating a MFX session: -9. |
| av1_qsv | no | - | - | [av1_qsv @ 0x56068bc63bc0] Error creating a MFX session: -9. |
| h264_vaapi | no | - | - | no DRI render node |
| hevc_vaapi | no | - | - | no DRI render node |
| av1_vaapi | no | - | - | no DRI render node |
| h264_v4l2m2m | no | - | - | [h264_v4l2m2m @ 0x5648fe14cbc0] Could not find a valid device |

- Hardware encoders compiled in: h264_nvenc, hevc_nvenc, av1_nvenc, h264_qsv, hevc_qsv, av1_qsv, h264_vaapi, hevc_vaapi, av1_vaapi, h264_v4l2m2m
- Hardware encoders that actually worked: none

## Storage
- /root: 60.0 GiB free of 252.0 GiB
- Sequential write (256 MiB, fsync): 920.4 MiB/s; read: 7294.6 MiB/s (likely cached)
- Media type: not_determined_by_script (SSD/HDD/network: confirm manually)

## Network
- Not measured: skipped by flag

## Thermal
- {"measured": false, "reason": "10-minute sustained-load test not run by default; use --thermal on laptops", "is_virtualised": true}

## Software
- python: Python 3.13.18
- node: v22.23.5
- npm: 10.9.9
- git: git version 2.43.0
- ffprobe: ffprobe version 6.1.1-3ubuntu5 Copyright (c) 2007-2023 the FFmpeg developers
- docker: Docker version 29.10.0, build fdd4b8e
- podman: absent
- uv: uv 0.11.32 (x86_64-unknown-linux-gnu)
- pip: pip 24.0 from /usr/lib/python3/dist-packages/pip (python 3.13)
- pandoc: pandoc 3.1.3
- brew: absent
- winget: absent

## Implications (provisional, see DECISIONS.md)

- No CUDA GPU: speech recognition runs on CPU (CTranslate2/int8 or whisper.cpp class runtimes); local vision-language models are likely too slow for dense use, so sample sparsely or use pre-screening.
- No working hardware encoder: drafts and finals both use software encoders; size render concurrency to cores.
- Concurrency starting point: at most 2 heavy media job(s) at once on 4 logical cores (to be tuned by measurement).
