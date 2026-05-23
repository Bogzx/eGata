// Wrappers around AudioWorklet — one for mic capture (PCM16 16 kHz)
// and one for agent playback (PCM16 24 kHz). Both keep the audio path
// off the main thread so React renders don't block frames.

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
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  const context = new AudioContext({ latencyHint: "interactive" });
  await context.audioWorklet.addModule("/worklets/pcm-recorder.js");
  const source = context.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(context, "pcm-recorder");
  node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => onChunk(e.data);
  source.connect(node);
  // Do NOT connect node→destination, otherwise the mic echoes through the speakers.
  return {
    context,
    source,
    node,
    stream,
    stop: () => {
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
  const context = new AudioContext({
    sampleRate: 24000,
    latencyHint: "interactive",
  });
  await context.audioWorklet.addModule("/worklets/pcm-player.js");
  const node = new AudioWorkletNode(context, "pcm-player");
  node.connect(context.destination);
  return {
    context,
    node,
    feed: (chunk: ArrayBuffer) => node.port.postMessage(chunk, [chunk]),
    flush: () => node.port.postMessage("flush"),
    stop: () => {
      try {
        node.disconnect();
      } catch {
        /* noop */
      }
      void context.close();
    },
  };
}
