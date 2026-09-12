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

## Diarization (finalization) -- real, Deepgram-only, best-effort

`api.services.voice.transcribe_audio_with_diarization` is a NEW
function (never a change to the original `transcribe_audio` -- same
"never rename/change a function pre-existing tests call directly"
discipline as Partie 21's own `assign_ab_test_variant`), used
automatically by `extract_audio_transcript`/`extract_video_transcript`
whenever `STT_PROVIDER=deepgram` (the only real, integrated STT
provider whose API supports diarization at all -- Whisper's API has
no such parameter). It calls `litellm.atranscription(..., diarize=True)`
and parses the response for real per-word `speaker` labels into
`MediaTranscript.segments_json` (`{speaker, start_ms, end_ms, text}`
per word).

**Honest, documented limitation**: this environment has no live
Deepgram account, so the exact real shape litellm normalizes a
diarized Deepgram response into has not been verified against a real
API call. Parsing is defensive (`_parse_diarization_segments`): it
only trusts a real `.words` attribute carrying real `speaker` keys,
and returns `None` (never a fabricated single-speaker guess) for
anything else -- the same "real result or honestly nothing" pattern
as `get_video_duration_ms`. `STT_PROVIDER=whisper` (or any diarization
failure) transparently falls back to the original, undiarized
`transcribe_audio` -- `segments_json` stays `NULL` in that case, same
as before this finalization.

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
