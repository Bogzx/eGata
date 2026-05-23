// Receives 24 kHz PCM16 chunks from the main thread, plays them through
// the AudioContext destination. Supports flush() for barge-in.
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.cursor = 0;
    this.port.onmessage = (e) => {
      if (e.data === "flush") {
        this.queue = [];
        this.cursor = 0;
        return;
      }
      const i16 = new Int16Array(e.data);
      const f32 = new Float32Array(i16.length);
      for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 32768;
      this.queue.push(f32);
    };
  }

  process(_inputs, outputs) {
    const out = outputs[0][0];
    let written = 0;
    while (written < out.length) {
      if (this.queue.length === 0) {
        for (let i = written; i < out.length; i++) out[i] = 0;
        return true;
      }
      const head = this.queue[0];
      const remain = head.length - this.cursor;
      const take = Math.min(remain, out.length - written);
      out.set(head.subarray(this.cursor, this.cursor + take), written);
      this.cursor += take;
      written += take;
      if (this.cursor >= head.length) {
        this.queue.shift();
        this.cursor = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-player", PCMPlayerProcessor);
