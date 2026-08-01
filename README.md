# Nativox — AI-Based System for Generating Native Language Dialogues in the Original Actor's Voice

A full-stack prototype of the Major Project system: upload a video, pick a
target language, and get back the same clip dubbed in that language —
using a clone of the *original actor's own voice* instead of a generic
dubbing artist.

```
dubbing-project/
├── backend/            FastAPI app — the 6-stage pipeline
│   ├── main.py          API routes
│   ├── app/
│   │   ├── config.py     settings (model sizes, engine choice, languages)
│   │   ├── jobs.py        in-memory job/progress store
│   │   ├── schemas.py     request/response models
│   │   └── pipeline/
│   │       ├── asr.py         Stage 1 — speech-to-text (faster-whisper)
│   │       ├── translate.py   Stage 2 — duration-aware translation
│   │       ├── tts.py         Stage 3/4 — voice cloning + prosody
│   │       ├── video_utils.py Stage 5 — stitch audio back onto video
│   │       ├── lipsync.py     Stage 6 — optional lip-sync (Wav2Lip)
│   │       └── orchestrator.py wires all stages + updates progress
│   └── requirements.txt
└── frontend/
    └── index.html       single-page dashboard UI (no build step needed)
```

## How it works

0. **Separate** *(new)* — Demucs splits the source audio into an isolated
   vocals track and a background (music/ambience) track. Everything else
   below runs on the vocals track; the background track is preserved
   untouched and mixed back in at the end. If Demucs isn't installed or
   fails on a clip, the pipeline logs it and falls back to working on the
   full mixed audio (old behavior) instead of crashing the job.
1. **ASR** — `faster-whisper` transcribes the (isolated) vocals with
   per-segment timestamps and a rough pace (words/sec) estimate.
2. **Translate** — each segment is translated (via `deep-translator`, free,
   no API key) and flagged if it will overrun the original segment's time
   budget, so it can be compressed to stay in sync — the same idea used by
   duration-based dubbing research in your literature review.
3. **Gender detection + voice synthesis** — the source voice's pitch (F0)
   is analyzed to classify it as male/female (`app/pipeline/gender_detect.py`);
   you can also override this from the UI. Synthesis uses Microsoft Edge's
   free neural TTS, which has real distinct male/female voices per
   language (`app/config.py: EDGE_VOICE_MAP`) — this is what makes gender
   selection actually work, since the previous gTTS-only setup had just
   one generic voice per language with nothing to choose between.
4. **Prosody + duration fit** — each synthesized line is time-stretched
   (pitch-preserving, via ffmpeg's `atempo` filter) to fit inside the gap
   before the *next* line starts — this is the fix for dubbed lines
   overlapping each other. As a hard backstop, the stitching step also
   force-trims any clip that still doesn't fit, so overlap is structurally
   impossible even in extreme cases.
5. **Mux** — the stitched dubbed vocals are layered onto the original
   background track (if separation succeeded) or used directly, then
   muxed onto the source video in place of the old audio.
6. **Lip-sync** *(optional/stretch goal)* — hook is in place for Wav2Lip;
   disabled by default since it needs a GPU and a separate install.

## Running it (3 steps)

**Mac/Linux:**
```bash
./run.sh
```

**Windows:** double-click `run.bat` (or run it in cmd/PowerShell).

Either script creates a virtual environment, installs everything from
`requirements.txt`, and starts the server. First run takes a few minutes
(downloading packages + the Whisper model); after that it starts in
seconds. Once it says `Uvicorn running on http://127.0.0.1:8000`, open
that URL in your browser — **the backend and frontend are the same app**,
served from one process.

You also need the `ffmpeg` binary installed system-wide (the scripts warn
you if it's missing):
```
Ubuntu/Debian: sudo apt install ffmpeg
Mac:           brew install ffmpeg
Windows:       https://ffmpeg.org/download.html  (add to PATH)
```

If you'd rather run the steps manually:
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```


## Upgrading to real voice cloning (the "futuristic" version)

By default `TTS_ENGINE=baseline` uses gTTS — this proves the whole pipeline
works end-to-end but doesn't actually clone the voice. To get real few-shot
voice cloning like the synopsis describes:

```bash
pip install TTS          # Coqui TTS — pulls in torch, ~2GB with the XTTS-v2 model
```

Then set the environment variable before starting the server:

```bash
export TTS_ENGINE=xtts       # Windows: set TTS_ENGINE=xtts
uvicorn main:app --reload
```

A GPU is strongly recommended for XTTS-v2 — on CPU it will work but each
line can take 10-30+ seconds to synthesize.

## Adding lip-sync

1. `git clone https://github.com/Rudrabha/Wav2Lip` next to the `backend/`
   folder (or wherever you set `WAV2LIP_DIR` in `app/pipeline/lipsync.py`).
2. Download their pretrained checkpoint per the Wav2Lip README and place it
   at `Wav2Lip/checkpoints/wav2lip_gan.pth`.
3. Set `ENABLE_LIPSYNC=true` before starting the server.

## Recent fixes

If you're updating from an earlier copy of this project, here's what changed:

| Problem | Fix |
|---|---|
| Dubbed audio segments overlapped each other | Each line is now time-fit to the gap before the *next* line starts (pitch-preserving speed-up via ffmpeg), plus a hard trim as a backstop — overlap is no longer possible |
| Male/female of the source speaker wasn't detected | Added real pitch (F0) analysis of the source voice (`gender_detect.py`) |
| Dubbing always defaulted to a female-sounding voice | Switched the TTS engine to Microsoft Edge neural TTS, which has real separate male/female voices per language; the old gTTS engine only ever had one generic voice, so there was nothing to select |
| Background music got wiped out in the dub | Added vocal/background separation (Demucs) — only the speech is replaced now; the original music/ambience track is preserved and mixed back in |

**Installing the new dependencies:** just rerun `pip install -r requirements.txt`
(or `./run.sh` / `run.bat` again) inside your existing venv — it'll pick up
`edge-tts`, `librosa`, `soundfile`, and `demucs`.

**A note on Demucs specifically:** it's the heaviest new dependency (~2GB,
includes `torch`, downloads a pretrained model the first time it runs) and
separation is noticeably slow on CPU — for a 20-second clip, expect maybe
30-90 seconds just for that step. This is normal. If you'd rather skip it
(e.g. for a fast demo where the source clip has no music anyway), set
`ENABLE_BACKGROUND_PRESERVATION=false` before starting the server; the
pipeline will just replace the full audio track like before, and the UI
will note in the transcript panel that background music wasn't preserved.

**A note on Edge TTS:** it calls a free Microsoft endpoint at synthesis
time, so it needs an internet connection (same as the translation and
Whisper-model-download steps already did). If it can't reach the endpoint,
it automatically falls back to gTTS for that line rather than failing the
whole job — you'd notice this as a less distinct male/female voice for
those specific lines.

- Translation compression for over-length segments is flagged but not
  actually paraphrased — swap in an LLM call with an explicit character
  budget for real duration-matching.
- The in-memory job store means progress is lost on server restart; swap
  `app/jobs.py` for Redis or a DB table for a production deployment.
- gTTS (baseline mode) requires internet access at synthesis time since it
  calls a Google endpoint; XTTS-v2 runs fully offline once its model is
  downloaded.
- Emotion transfer here is a simple pace-matching heuristic, not full
  affect transfer — a genuine emotion-embedding model (as discussed in your
  literature review, ref [8]-[11]) is the natural next research step.

## Suggested demo flow for your viva

1. Upload a short (10-30s) clip with one speaker talking clearly.
2. Pick a target language and hit **Start dubbing**.
3. Point at the pipeline strip lighting up stage by stage — this alone
   demonstrates you understand and can explain every part of the ASR →
   MT → TTS → mux chain.
4. Play the source and dubbed clips side by side.
5. Talk through the "Known limits" section above and the upgrade path to
   XTTS-v2 + Wav2Lip — examiners respond well to a clear, honest roadmap
   from working prototype to the full envisioned system.

## Turning this into a "proper app"

Right now it's a local web app — great for development and demos on your
own machine, but only reachable at `127.0.0.1`. Here's the path from that
to something you can actually hand someone a link or an icon for,
depending on what "proper app" means for your submission:

### Option A — a real website (easiest, recommended for a viva)
Deploy the FastAPI backend (which already serves the frontend) to a free
host, so classmates/examiners can open a real URL instead of localhost.
- **Render.com** (simplest): New → Web Service → connect this repo →
  build command `pip install -r backend/requirements.txt`, start command
  `uvicorn main:app --host 0.0.0.0 --port $PORT` with root dir `backend`.
  Free tier is enough for a demo (it sleeps when idle, wakes on request).
- **Railway.app**: similar one-click flow, detects the `requirements.txt`
  automatically.
- Note: free tiers usually have no GPU, so keep `TTS_ENGINE=baseline` (or
  use a small XTTS setup) and process short clips only.

### Option B — an installable web app (PWA)
The frontend already ships with `manifest.json`, so once it's deployed
(Option A), visiting the site on a phone or desktop Chrome/Edge shows an
"Install app" prompt — it then runs in its own window with its own icon,
no browser chrome. This is the lowest-effort way to make it feel like a
native app without writing a separate mobile/desktop codebase.

### Option C — a desktop .exe/.app
Wrap the same frontend in a native window using **pywebview**:
```bash
pip install pywebview
```
```python
# desktop.py — run this instead of opening a browser
import threading, webview
import uvicorn

def start_server():
    uvicorn.run("main:app", host="127.0.0.1", port=8000)

threading.Thread(target=start_server, daemon=True).start()
webview.create_window("Nativox", "http://127.0.0.1:8000")
webview.start()
```
Then package it into a single executable with `pyinstaller desktop.py`.
This gives you a real double-clickable desktop app with no browser tab.

### Option D — a mobile app
The realistic path is **not** rewriting this in Swift/Kotlin — it's
Option B (PWA) for "install from a link," or wrapping the deployed website
in a thin native shell with **Capacitor** if you specifically need an
`.apk`/App Store build for your submission. Either way, deploy the backend
first (Option A) — a mobile app still needs a real server to talk to,
since video/AI processing can't run entirely on a phone.

**Recommendation for a college major project**: do Option A (deploy to
Render) plus mention Option B/C as "future work" in your report — that's
enough to demo live from a shareable link, which is what most examiners
actually want to see.
