import {WyomingEvent} from './proto/hassmic';

export type SatelliteEventPayload = WyomingEvent['event'];

/** Build a control-plane satellite event that cannot be confused with another turn. */
export function createSatelliteEvent(
  turnId: string,
  event: SatelliteEventPayload,
): WyomingEvent {
  if (!turnId.trim()) {
    throw new Error('Satellite events require a turn identifier');
  }

  return WyomingEvent.create({turnId, event});
}

/** Reject stale acknowledgements after a reconnect, cancellation, or next turn. */
export function isCurrentTurnEvent(
  event: Pick<WyomingEvent, 'turnId'>,
  activeTurnId: string | null,
): boolean {
  return activeTurnId !== null && event.turnId === activeTurnId;
}
