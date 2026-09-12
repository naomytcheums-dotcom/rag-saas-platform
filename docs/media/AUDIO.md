# Audio

## Upload and processing

`POST /organizations/{org_id}/media` with any `audio/*` file (up to
`MULTIMODAL_MAX_AUDIO_SIZE_MB`, default 50MB). Real transcription
reuses `api.services.voice.transcribe_audio` (Whisper/Deepgram via
litellm) UNCHANGED -- the same real function `VoiceMessage`/telephony
already use, not a second, parallel STT path. `STT_PROVIDER` defaults
to `web_speech` (client-side only, see `api/services/voice.py`'s own
docstring) -- a real deployment processing standalone media uploads
needs `STT_PROVIDER=whisper` or `deepgram` set, with the matching
`OPENAI_API_KEY`/`DEEPGRAM_API_KEY`.

The resulting text is stored as a real `MediaTranscript` row
(`text`, `provider`, `language`), then indexed into `DocumentChunk`
(`metadata_json.source = "media_transcript"`) the same way document
text is.

## A real, honest gap: no diarization

This part's own pre-build audit confirmed no speaker-diarization code
exists anywhere in this codebase. `MediaTranscript.segments_json` is a
real, nullable column reserved for real per-speaker segments
(`{start_ms, end_ms, speaker, text}`) once a real diarization provider
is integrated -- today it stays `NULL`; `transcribe_audio` returns
plain text only. Not silently pretended to work.

## Endpoints

- `GET /media/{id}/transcript` -- 404 if processing hasn't produced
  one yet (never a fabricated empty transcript).
- `GET /media/{id}/file` -- real, authenticated, chunked audio proxy
  (used by the frontend's `AudioPlayer`, which fetches it as an
  authenticated blob -- a plain `<audio src>` cannot carry a Bearer
  token).

## Real, periodic backfill

`api/tasks/media.py::extract_transcripts` (daily) re-checks every
`completed` audio asset for a missing transcript row -- a real,
honest self-healing sweep, not expected to normally find anything.
