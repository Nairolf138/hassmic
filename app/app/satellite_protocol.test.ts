import {
  createSatelliteEvent,
  isCurrentTurnEvent,
} from './satellite_protocol';

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
});
