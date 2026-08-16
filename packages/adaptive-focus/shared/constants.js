/** Shared constants for Adaptive Focus */

export const STORAGE_KEY = 'af_session_v1'
export const SETTINGS_KEY = 'af_settings_v1'

export const DEFAULT_SETTINGS = {
  focusMin: 25,
  shortBreakMin: 5,
  longBreakMin: 15,
  sessionsBeforeLong: 4,
  maxFocusMin: 45,
  extendMin: 5,
  lockClassic: false,
  sensitivity: 'normal', // calm | normal | sensitive
}

export const MODE = {
  IDLE: 'idle',
  FOCUS: 'focus',
  BREAK: 'break',
  BREATH: 'breath',
}

export const MOTION = {
  STILL: 'still',
  TYPING: 'typing',
  FIDGET: 'fidget',
  WALK: 'walk',
  UNKNOWN: 'unknown',
}

export const AUTO = {
  CALM: 'calm',
  ENGAGED: 'engaged',
  LOADED: 'loaded',
  SPIKE: 'spike',
}

export const PHASE = {
  NORMAL: 'normal',
  ZONE: 'zone',
  FATIGUE: 'fatigue',
  SPIKE: 'spike',
}
