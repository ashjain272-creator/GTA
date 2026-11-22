# Licence Matrix (spec 3.3 rights, R17, P1-04)

Checked 2026-11-22. The intended use is that the operator runs the software
privately and publishes the rendered videos, possibly commercially.
`tests/unit/test_licences.py` fails if any installed Python distribution has a
copyleft or unknown licence that is not listed here.

## Python dependencies (from installed metadata of the uv.lock environment)

| Package | Version | Licence | Use OK? |
|---|---|---|---|
| faster-whisper | 1.2.1 | MIT | yes |
| ctranslate2 | 4.9.0 | MIT | yes |
| onnxruntime | 1.32.0 | MIT | yes |
| av (PyAV) | 19.0.2 | BSD-3-Clause | yes (not used directly, E-019) |
| numpy | 2.5.5 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | yes |
| huggingface_hub, hf-xet, tokenizers | 2.4.0 / 1.8.0 / 0.23.3 | Apache-2.0 | yes |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | yes. MPL is file-level copyleft and applies only if tqdm itself is modified and distributed |
| certifi (if resolved) | 2026.x | MPL-2.0 | yes. A CA certificate bundle used unmodified |
| PyYAML, jsonschema, referencing, rpds-py, attrs, anyio, h11, filelock, pluggy, iniconfig, pytest, truststore | various | MIT | yes |
| click, fsspec, httpx2, httpcore2, idna, protobuf, Pygments | various | BSD-2/3-Clause | yes |
| flatbuffers, packaging | various | Apache-2.0 (packaging: Apache-2.0 OR BSD-2-Clause) | yes |
| typing_extensions | 4.16.0 | PSF-2.0 | yes |

## Model weights

| Model | Licence | Source | Status |
|---|---|---|---|
| Systran/faster-whisper-{tiny,base,small}.en (CTranslate2 conversions) | MIT | Hugging Face model API `cardData.license` | VERIFIED 2026-11-22 (E-030) |
| openai/whisper-base.en (upstream weights) | Apache-2.0 per its Hugging Face card | Hugging Face model API | VERIFIED 2026-11-22 (E-030). Note: OpenAI's GitHub repository states MIT; both permit commercial use |
| Silero VAD v6 (bundled in faster-whisper as `assets/silero_vad_v6.onnx`) | MIT (upstream silero-vad repository) | not read at source | SECONDARY |

## System tools (invoked as separate processes, never linked)

| Tool | Licence | Implication |
|---|---|---|
| FFmpeg 6.1.1 (Ubuntu build, `--enable-gpl`, includes libx264) | GPL-2.0-or-later as built | Running it as a subprocess does not place clipops under the GPL. Videos it encodes are not encumbered by the encoder's licence. Redistributing a bundled FFmpeg binary would require GPL compliance, so the runbook installs FFmpeg from the OS package manager instead. |
| espeak-ng 1.51 | GPL-3.0-or-later | Used only by `scripts/make_synthetic_fixture.py` to make test audio. Not distributed. Generated speech treated as unencumbered (A-012). |
| libass (inside FFmpeg) | ISC | yes |

## Assets

No fonts, music, sound effects or graphics are registered yet. Captions use the
system font "DejaVu Sans" (Bitstream Vera licence plus public-domain changes;
permits embedding in rendered video). The asset registry (spec A.3) is
required before any further asset is used (ROADMAP P0-14).

## Watch list

- pyannote diarisation models are gated on Hugging Face and some are
  non-commercial. Check before decision 5.6 #5.
- Any NVIDIA, Intel or AMD runtime added for hardware acceleration needs its
  redistribution terms checked.
