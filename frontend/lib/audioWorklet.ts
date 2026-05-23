// Wrappers around AudioWorklet — one for mic capture (PCM16 16 kHz)
// and one for agent playback (PCM16 24 kHz). Both keep the audio path
// off the main thread so React renders don't block frames.

const LOG = (...args: unknown[]) =>
  console.log("[civicai:audio]", ...args);
const WARN = (...args: unknown[]) =>
  console.warn("[civicai:audio]", ...args);

export type RecorderHandle = {
  context: AudioContext;
  source: MediaStreamAudioSourceNode;
  node: AudioWorkletNode;
  stream: MediaStream;
  stop: () => void;
};

export async function startMicRecorder(
  onChunk: (chunk: ArrayBuffer) => void,
): Promise<RecorderHandle> {
  LOG("startMicRecorder — requesting getUserMedia");
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  const tracks = stream.getAudioTracks();
  LOG(
    "mic stream obtained — tracks:",
    tracks.length,
    tracks.map((t) => ({
      label: t.label,
      muted: t.muted,
      enabled: t.enabled,
      settings: t.getSettings(),
    })),
  );

  // Match the recorder context to Gemini Live's expected input rate
  // (16 kHz) so the browser handles the downsample on the input node with
  // a proper anti-alias filter, rather than the worklet trying to decimate
  // by hand. Older recorders ran the context at the system default
  // (typically 48 kHz) and the worklet did nearest-neighbour downsampling,
  // which folded high frequencies back into the voice band and made
  // Romanian transcription unreliable. Some platforms ignore the hint and
  // pick a different rate; the worklet adapts at runtime via `sampleRate`.
  const context = new AudioContext({
    sampleRate: 16000,
    latencyHint: "interactive",
  });
  LOG("AudioContext created — sampleRate:", context.sampleRate);
  await context.audioWorklet.addModule("/worklets/pcm-recorder.js");
  LOG("pcm-recorder worklet module loaded");
  const source = context.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(context, "pcm-recorder");
  let chunkCount = 0;
  let lastLogAt = 0;
  node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
    chunkCount += 1;
    if (chunkCount === 1 || Date.now() - lastLogAt > 2000) {
      LOG(
        "mic chunk #" + chunkCount,
        "bytes:",
        e.data.byteLength,
        "(expect 3200 for 100ms @ 16kHz PCM16)",
      );
      lastLogAt = Date.now();
    }
    onChunk(e.data);
  };
  source.connect(node);
  // Do NOT connect node→destination, otherwise the mic echoes through the speakers.
  LOG("mic recorder wired — chunks will flow");
  return {
    context,
    source,
    node,
    stream,
    stop: () => {
      LOG("mic recorder stop — total chunks emitted:", chunkCount);
      try {
        node.disconnect();
      } catch {
        /* noop */
      }
      try {
        source.disconnect();
      } catch {
        /* noop */
      }
      stream.getTracks().forEach((t) => t.stop());
      void context.close();
    },
  };
}

export type PlayerHandle = {
  context: AudioContext;
  node: AudioWorkletNode;
  feed: (chunk: ArrayBuffer) => void;
  flush: () => void;
  stop: () => void;
};

export async function startPlayer(): Promise<PlayerHandle> {
  LOG("startPlayer — creating 24kHz AudioContext");
  const context = new AudioContext({
    sampleRate: 24000,
    latencyHint: "interactive",
  });
  LOG("player AudioContext sampleRate:", context.sampleRate);
  await context.audioWorklet.addModule("/worklets/pcm-player.js");
  LOG("pcm-player worklet module loaded");
  const node = new AudioWorkletNode(context, "pcm-player");
  node.connect(context.destination);
  let fedChunks = 0;
  let lastLogAt = 0;
  return {
    context,
    node,
    feed: (chunk: ArrayBuffer) => {
      fedChunks += 1;
      if (fedChunks === 1 || Date.now() - lastLogAt > 2000) {
        LOG("player feed #" + fedChunks, "bytes:", chunk.byteLength);
        lastLogAt = Date.now();
      }
      node.port.postMessage(chunk, [chunk]);
    },
    flush: () => {
      LOG("player flush (barge-in)");
      node.port.postMessage("flush");
    },
    stop: () => {
      LOG("player stop — total chunks fed:", fedChunks);
      try {
        node.disconnect();
      } catch {
        /* noop */
      }
      void context.close();
    },
  };
}
void WARN;

