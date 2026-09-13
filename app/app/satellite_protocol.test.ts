import {
  createSatelliteEvent,
  isCurrentTurnEvent,
  SatelliteTransport,
} from './satellite_protocol';
import {WyomingEvent} from './proto/hassmic';

describe('satellite event correlation', () => {
  it('tags an audio event with the active turn identifier', () => {
    expect(
      createSatelliteEvent('turn-42', {
        oneofKind: 'audioStart',
        audioStart: {rate: 16000, width: 2, channels: 1},
      }),
    ).toMatchObject({
      turnId: 'turn-42',
      event: {oneofKind: 'audioStart'},
    });
  });

  it('rejects an acknowledgement belonging to an old turn', () => {
    const delayedPlayed = createSatelliteEvent('turn-old', {
      oneofKind: 'played',
      played: {},
    });

    expect(isCurrentTurnEvent(delayedPlayed, 'turn-current')).toBe(false);
  });

  it('emits microphone audio only for the active turn', () => {
    const sent: WyomingEvent[] = [];
    const transport = new SatelliteTransport(event => sent.push(event));
    transport.begin('turn-42');

    transport.sendMicrophoneAudio(new Uint8Array([1, 2, 3]));

    expect(sent).toHaveLength(1);
    expect(sent[0]).toMatchObject({
      turnId: 'turn-42',
      event: {oneofKind: 'audioChunk'},
      payload: new Uint8Array([1, 2, 3]),
    });
  });

  it('does not emit microphone audio after the turn ends', () => {
    const sent: WyomingEvent[] = [];
    const transport = new SatelliteTransport(event => sent.push(event));
    transport.begin('turn-42');
    transport.end('turn-42');

    transport.sendMicrophoneAudio(new Uint8Array([1, 2, 3]));

    expect(sent).toHaveLength(0);
  });
});
