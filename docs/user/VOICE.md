# Voice

If enabled by your organization, you can interact with the assistant by
voice.

## Asking by voice

Use the microphone button above the chat input to dictate a question.

## Listening to answers

Toggle **Read answers aloud** to have responses read back to you.
Citation markers, code blocks, and markdown formatting are stripped
before text-to-speech, so what you hear is the plain answer text.

## Requirements

Voice features rely on your browser's speech APIs — a Chromium-based
browser gives the most consistent experience, and microphone access
generally requires HTTPS (or `localhost` in development). If the mic
button doesn't respond, check your browser's microphone permission for
the site.

## Voice messages

Depending on configuration, voice input/output may also be available in
external channels (e.g. via Twilio) — see
[Voice Messages settings](../admin/DASHBOARD.md) for admin
configuration.
