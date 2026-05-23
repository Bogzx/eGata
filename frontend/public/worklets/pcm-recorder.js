// Captures mic audio at AudioContext rate, resamples to 16 kHz PCM16,
// posts ArrayBuffer chunks (~100 ms each) to the main thread.
class PCMRecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetRate = 16000;
    this.sourceRate = sampleRate; // AudioContext sample rate (often 48000)
    this.ratio = this.sourceRate / this.targetRate;
    this.acc = [];
    this.chunkSamples = 1600; // 100 ms at 16 kHz
    this._pos = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const ch = input[0];

    // Naive nearest-neighbour downsample (good enough for speech).
    for (let i = 0; i < ch.length; i++) {
      this._pos += 1;
      if (this._pos >= this.ratio) {
        this.acc.push(ch[i]);
        this._pos -= this.ratio;
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
