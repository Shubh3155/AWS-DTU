export type ActiveGuidance = {
  journeyId: string; routeVersion: string; expiresAt: number; lastDisplayedSequence: number;
  clientId?: string;
};
export type DirectionAlert = {
  journeyId: string; routeVersion: string; sequence: string; instruction: string;
  issuedAt: string; expiresAt: string;
};

export function validDirectionAlert(data: Partial<DirectionAlert> | undefined, active: ActiveGuidance | null, now = Date.now()): data is DirectionAlert {
  if (!data || !active || active.expiresAt <= now || data.journeyId !== active.journeyId || data.routeVersion !== active.routeVersion) return false;
  const sequence = Number(data.sequence), issued = Number(data.issuedAt), expires = Number(data.expiresAt);
  return Number.isInteger(sequence) && sequence > active.lastDisplayedSequence
    && Number.isFinite(issued) && Number.isFinite(expires) && issued <= now + 5000
    && issued >= now - 15000 && expires > now && expires <= issued + 15000
    && typeof data.instruction === "string" && data.instruction.length > 0 && data.instruction.length <= 1200;
}
