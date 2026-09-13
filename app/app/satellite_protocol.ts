import {WyomingEvent} from './proto/hassmic';

export type SatelliteEventPayload = WyomingEvent['event'];

/** Build a control-plane satellite event that cannot be confused with another turn. */
export function createSatelliteEvent(
  turnId: string,
  event: SatelliteEventPayload,
  payload: Uint8Array = new Uint8Array(),
): WyomingEvent {
  if (!turnId.trim()) {
    throw new Error('Satellite events require a turn identifier');
  }

  return WyomingEvent.create({turnId, event, payload});
}

export type SatelliteEventEmitter = (event: WyomingEvent) => void;

/**
 * Routes microphone PCM over Cheyenne only while Home Assistant owns a turn.
 * The caller supplies the transport so this state machine stays testable.
 */
export class SatelliteTransport {
  private activeTurnId: string | null = null;

  constructor(private readonly emit: SatelliteEventEmitter) {}

  begin(turnId: string): void {
    if (!turnId.trim()) {
      throw new Error('Satellite turns require an identifier');
    }
    this.activeTurnId = turnId;
  }

  end(turnId: string): void {
    if (this.activeTurnId === turnId) {
      this.activeTurnId = null;
    }
  }

  sendMicrophoneAudio(payload: Uint8Array): void {
    if (!this.activeTurnId) {
      return;
    }

    this.emit(
      createSatelliteEvent(
        this.activeTurnId,
        {
          oneofKind: 'audioChunk',
          audioChunk: {rate: 16000, width: 2, channels: 1},
        },
        payload,
      ),
    );
  }
}

/** Reject stale acknowledgements after a reconnect, cancellation, or next turn. */
export function isCurrentTurnEvent(
  event: Pick<WyomingEvent, 'turnId'>,
  activeTurnId: string | null,
): boolean {
  return activeTurnId !== null && event.turnId === activeTurnId;
}
