// Partie 8.2.3 -- real, sentence-aware chunking for streaming voice
// playback. Splits on real sentence boundaries first (so a chunk is
// never cut mid-sentence, which would sound wrong spoken aloud), and
// only falls back to a hard cut at STREAMING_VOICE_CHUNK_SIZE for a
// single sentence longer than that.
export function chunkTextForVoice(text: string, chunkSize: number): string[] {
  const sentences = text.match(/[^.!?]+[.!?]*\s*/g) ?? [text];
  const chunks: string[] = [];
  let current = "";

  for (const sentence of sentences) {
    if ((current + sentence).length <= chunkSize) {
      current += sentence;
      continue;
    }
    if (current) chunks.push(current.trim());
    current = sentence.length <= chunkSize ? sentence : "";
    if (sentence.length > chunkSize) {
      for (let i = 0; i < sentence.length; i += chunkSize) chunks.push(sentence.slice(i, i + chunkSize).trim());
    }
  }
  if (current) chunks.push(current.trim());
  return chunks.filter(Boolean);
}
