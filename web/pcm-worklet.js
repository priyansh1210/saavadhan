// Turns the microphone into 16 kHz, 16-bit mono PCM frames of 512 samples (1024 bytes),
// which is exactly what Gnani Prisma's realtime endpoint expects.
class Pcm16kProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.pos = 0;            // fractional read position into the incoming stream
    this.prev = 0;           // last sample of the previous block, for interpolation
    this.out = new Int16Array(512);
    this.n = 0;
    this.level = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    let peak = 0;
    // Linear-interpolation resampler from sampleRate to 16 kHz.
    while (this.pos < ch.length) {
      const i = Math.floor(this.pos);
      const frac = this.pos - i;
      const a = i === 0 ? this.prev : ch[i - 1];
      const b = ch[i];
      let s = a + (b - a) * frac;
      s = Math.max(-1, Math.min(1, s));
      peak = Math.max(peak, Math.abs(s));
      this.out[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      if (this.n === 512) {
        this.port.postMessage(this.out.buffer.slice(0));
        this.n = 0;
      }
      this.pos += this.ratio;
    }
    this.pos -= ch.length;
    this.prev = ch[ch.length - 1];
    this.level = Math.max(peak, this.level * 0.9);
    if ((this.tick = (this.tick || 0) + 1) % 8 === 0) this.port.postMessage({ level: this.level });
    return true;
  }
}

registerProcessor("pcm16k", Pcm16kProcessor);
