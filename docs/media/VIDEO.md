# Video

This part's own pre-build audit confirmed video is a total green
field in this codebase (no ffmpeg/opencv/frame-extraction code
anywhere) -- everything below is genuinely new.

## Real, system-binary dependency

`api/services/video_extraction.py` shells out to real `ffmpeg`/
`ffprobe` binaries via `subprocess` -- the exact same category of
dependency as Tesseract/poppler (`api/services/ocr.py`'s own
docstring): never a pip package, a real, separate system binary a
production deployment (and CI) must install. `FFmpegNotAvailableError`
distinguishes "the binary just isn't installed" from any other real
failure, so a missing binary degrades a `MediaAsset` gracefully
(processing continues for whatever real steps CAN run) rather than
crashing outright.

## Processing (`api/services/media.py::process_media_asset`)

Upload any `video/*` file (up to `MULTIMODAL_MAX_VIDEO_SIZE_MB`,
default 200MB). Real, per-step resilience -- a missing ffmpeg binary
or a real transcription-provider failure on ANY one step logs a
warning and lets the others still run:

1. **Duration** -- real `ffprobe` probe (`get_video_duration_ms`),
   stored on `MediaAsset.duration_ms`.
2. **Audio-track extraction + transcription** -- `ffmpeg` extracts a
   real 16kHz mono WAV audio track, then hands it to the SAME real
   `transcribe_audio` (`api/services/voice.py`) a native audio upload
   uses -- stored as a real `MediaTranscript` row, not a separate,
   video-specific transcription path.
3. **Frame extraction** -- `ffmpeg` extracts evenly-spaced frames
   (`MULTIMODAL_FRAME_INTERVAL_SECONDS`, default every 5s), capped at
   `MULTIMODAL_MAX_FRAMES_PER_VIDEO` (default 20) -- a real, stated
   limit against an unbounded frame count for a very long video. Each
   frame is uploaded to S3 and described by the SAME real vision-LLM
   call images use (`describe_image`), stored as a real `MediaFrame`
   row.
4. **Video summary** -- once every real frame has its own real
   description, `describe_video` sends them (in chronological order)
   to the SAME LLM for a real, 2-3 sentence summary, stored as
   `MediaAsset.description`.
5. **RAG indexing** -- the real transcript, every real frame
   description, and the real video summary are each chunked/embedded
   and stored as `DocumentChunk` rows, tagged `media_transcript` /
   `media_frame_description` / `media_video_summary` respectively.

## Endpoints

- `GET /media/{id}/frames` -- every real extracted frame
  (`frame_index`, `timestamp_ms`, `description`, `objects_json`).
- `GET /media/{id}/frames/{frame_id}/file` -- real, authenticated,
  chunked proxy to one frame's own JPEG bytes.
- `GET /media/{id}/transcript` -- the video's own real audio-track
  transcript (same shape as a native audio upload's).

## Real, periodic backfill

`extract_frames` and `extract_transcripts` (daily Celery jobs) re-check
every `completed` video asset for missing frames/transcripts -- real
self-healing, e.g. after ffmpeg was installed AFTER an asset finished
processing without it.
