// allows playing PCM streams

import { NativeModules } from "react-native";
// fork at https://github.com/jeffc/react-native-pcm-audio
const { PcmAudio } = NativeModules;
import { HMLogger } from "./logger";
import { Buffer } from "buffer";

const Logger = new HMLogger("pcm.ts");

class PCMPlayer_ {
  private completionResolvers = new Map<number, () => void>();

  // Based on examples at
  // https://github.com/clshortfuse/react-native-pcm-audio
  startAudioStream = (pcmOptions: any): Promise<number> => {
    return new Promise<number>((resolve, reject) => {
      let sessionId: number | null = null;
      var callback = (event: string, data: any) => {
        switch (event) {
          case "onSessionId":
            /* start playing audio immediately */
            Logger.info(`Got audio session id: ${data}`);
            sessionId = data;
            resolve(data);
            break;
          case "onAudioDone":
            Logger.info(`Audio session done: ${data}`);
            if (sessionId !== null) {
              this.completionResolvers.get(sessionId)?.();
              this.completionResolvers.delete(sessionId);
            }
            break;
        }
      };
      PcmAudio.build(pcmOptions, callback);
    }).then((id: number): number => {
      NativeModules.PcmAudio.play(id);
      return id;
    });
  };

  writeAudioStream = async (id: number, samples: Uint8Array) => {
    if (!samples) {
      Logger.error("Not writing null samples");
      return;
    } else if (!id) {
      Logger.error("No audio session ID");
      return;
    }
    /* write pcm samples here */
    var base64Data = Buffer.from(samples).toString("base64");
    await PcmAudio.write(id, base64Data);
  };

  stopAudioStream = async (id: number) => {
    if (!id) {
      Logger.info("no audio stream");
      return;
    }

    const completed = new Promise<void>(resolve => {
      this.completionResolvers.set(id, resolve);
    });
    PcmAudio.end(id);
    await Promise.race([
      completed,
      new Promise<void>(resolve => setTimeout(resolve, 8000)),
    ]);
    this.completionResolvers.delete(id);
  };

  // Play a short local cue without involving Home Assistant TTS.
  // This is used for wake-word feedback so the user knows that recording
  // has started before the Assist response is generated.
  playTone = async (
    frequency = 880,
    durationMs = 110,
    volume = 0.28,
  ) => {
    const sampleRate = 22050;
    const sampleCount = Math.max(
      1,
      Math.round((sampleRate * durationMs) / 1000),
    );
    const samples = new Uint8Array(sampleCount * 2);
    const view = new DataView(samples.buffer);
    const amplitude = Math.max(0, Math.min(1, volume)) * 32767;
    for (let i = 0; i < sampleCount; i++) {
      const envelope = Math.min(
        1,
        i / Math.max(1, sampleRate * 0.008),
        (sampleCount - i) / Math.max(1, sampleRate * 0.018),
      );
      const value = Math.round(
        Math.sin((2 * Math.PI * frequency * i) / sampleRate) *
          amplitude *
          envelope,
      );
      view.setInt16(i * 2, value, true);
    }

    const streamId = await this.startAudioStream({
      encoding: '16bit',
      usage: 'notification',
      sampleRate,
      channels: 1,
      mode: 'streaming',
      gain: 1,
    });
    await this.writeAudioStream(streamId, samples);
    await new Promise(resolve => setTimeout(resolve, durationMs));
    await this.stopAudioStream(streamId);
  };

  setGain = async (id: number, gain: number) => {
    if (!id) {
      Logger.info("no audio stream");
    }
    if (!(0 <= gain && gain <= 1)) {
      Logger.error(`Invalid gain setting for stream ID ${id}: ${gain}`);
      return;
    }
    PcmAudio.setGain(id, gain);
  };

  getGain = async (id: number) => {
    if (!id) {
      Logger.info("no audio stream");
    }
    return PcmAudio.getGain(id);
  };
}

export const PCMPlayer = new PCMPlayer_();
