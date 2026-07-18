/**
 * CALT phone pairing payload — encode in QR on web, decode in Android.
 * Prefix makes scanners unambiguous.
 */
export const CALT_PAIR_PREFIX = "CALT1:";

export type CaltPairPayload = {
  v: 1;
  kind: "calt-pair";
  api: string;
  token: string;
  user?: string;
  issuedAt: string;
};

export function buildCaltPairPayload(opts: {
  apiBaseUrl: string;
  token: string;
  username?: string | null;
}): CaltPairPayload {
  return {
    v: 1,
    kind: "calt-pair",
    api: opts.apiBaseUrl.replace(/\/$/, ""),
    token: opts.token,
    user: opts.username ?? undefined,
    issuedAt: new Date().toISOString(),
  };
}

export function encodeCaltPairPayload(payload: CaltPairPayload): string {
  return `${CALT_PAIR_PREFIX}${JSON.stringify(payload)}`;
}
