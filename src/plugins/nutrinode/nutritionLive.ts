export const NUTRINODE_LIVE_WS_KEY = "nutrinode:live_ws";
export const NUTRINODE_LIVE_WS_EVENT = "nutrinode:live_ws";

export function isNutritionLiveWsEnabled(): boolean {
  try {
    return localStorage.getItem(NUTRINODE_LIVE_WS_KEY) === "true";
  } catch {
    return false;
  }
}

export function setNutritionLiveWsEnabled(on: boolean): void {
  localStorage.setItem(NUTRINODE_LIVE_WS_KEY, on ? "true" : "false");
  window.dispatchEvent(new Event(NUTRINODE_LIVE_WS_EVENT));
}
