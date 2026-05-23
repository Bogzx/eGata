// Captures mic audio at the AudioContext rate, downsamples to 16 kHz
// PCM16, and posts ArrayBuffer chunks (~100 ms each) to the main thread.
//
// The main thread tries to open the context at 16 kHz so the browser
// handles the resample on the input node with a proper anti-alias filter
// (which sounds dramatically better than nearest-neighbour decimation in
// JS — the prior worklet aliased high frequencies into the voice band and
// made Romanian sibilants almost unrecognisable to Gemini). If the browser
// honours the hint, `sampleRate` is 16000 and the worklet just chunks
// straight through. If it does not (e.g. some Safari/Firefox builds
// quantise to the device rate), we fall back to a single-pole low-pass
// followed by polyphase nearest-sample picking — still better than the
// raw nearest-neighbour version this replaces.
//
// Chunk size guideline (Gemini Live):
//   - Too small (<100 ms) → VAD gets noisy, may split words.
//   - Too big (>500 ms) → end-of-turn detection lags.
//   - 100 ms (1600 samples @ 16 kHz) sits at the lower-latency edge of
//     the safe range.
const TARGET_RATE = 16000;

class PCMRecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetRate = TARGET_RATE;
    this.sourceRate = sampleRate; // AudioWorklet global
    this.passthrough = this.sourceRate === this.targetRate;
    this.ratio = this.sourceRate / this.targetRate;
    this.acc = [];
    this.chunkSamples = 1600; // 100 ms at 16 kHz

    // Single-pole low-pass for the fallback path. Cut-off ~ targetRate/2.
    // y[n] = y[n-1] + alpha * (x[n] - y[n-1])
    // alpha = dt / (rc + dt), rc = 1 / (2*pi*fc)
    const fc = this.targetRate / 2;
    const dt = 1 / this.sourceRate;
    const rc = 1 / (2 * Math.PI * fc);
    this.alpha = dt / (rc + dt);
    this.lpState = 0;
    this._pos = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const ch = input[0];

    if (this.passthrough) {
      for (let i = 0; i < ch.length; i++) this.acc.push(ch[i]);
    } else {
      for (let i = 0; i < ch.length; i++) {
        this.lpState += this.alpha * (ch[i] - this.lpState);
        this._pos += 1;
        if (this._pos >= this.ratio) {
          this.acc.push(this.lpState);
          this._pos -= this.ratio;
        }
      }
    }

    while (this.acc.length >= this.chunkSamples) {
      const slice = this.acc.splice(0, this.chunkSamples);
      const pcm = new Int16Array(slice.length);
      for (let j = 0; j < slice.length; j++) {
        const s = Math.max(-1, Math.min(1, slice[j]));
        pcm[j] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor("pcm-recorder", PCMRecorderProcessor);
