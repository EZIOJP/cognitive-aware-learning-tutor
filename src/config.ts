/**
 * Configuration file for EEG AI Math Tutor
 * Modify these values to customize the application behavior
 */

export const config = {
  /**
   * Backend connection settings
   */
  backend: {
    // WebSocket URL for real-time EEG data stream
    websocketUrl: 'ws://localhost:8000/ws/eeg',

    // HTTP URL for API calls (interventions, logging)
    apiUrl: 'http://localhost:8000',

    // Reconnection settings
    maxReconnectAttempts: 5,
    reconnectDelay: 2000, // milliseconds
  },

  /**
   * Cognitive load thresholds
   * Adjust these based on your personal EEG baseline
   */
  cognitiveLoad: {
    // Gamma wave thresholds (0-100 scale)
    highThreshold: 60,   // Above this = high cognitive load
    mediumThreshold: 35, // Above this = medium cognitive load
    // Below mediumThreshold = low cognitive load

    // Alternative: Use weighted formula instead of simple gamma threshold
    useWeightedFormula: false,
    weights: {
      gamma: 0.6,   // Stress indicator
      beta: 0.3,    // Focus indicator
      alpha: -0.1,  // Relaxation (inverse correlation with load)
    },
  },

  /**
   * AI Intervention triggers
   */
  intervention: {
    // Master switch — set false to hide AI tutor popups (prototype)
    enabled: false,

    // Gamma threshold to trigger intervention
    gammaThreshold: 70,

    // Seconds of canvas inactivity before checking for intervention
    inactivityThreshold: 45,

    // Minimum time between interventions (seconds)
    minTimeBetweenInterventions: 120,

    // Enable automatic interventions (vs manual trigger only)
    autoTrigger: false,
  },

  /**
   * Pomodoro timer settings
   */
  pomodoro: {
    // Work session duration (minutes)
    workDuration: 25,

    // Short break duration (minutes)
    shortBreak: 5,

    // Long break duration (minutes)
    longBreak: 15,

    // Number of sessions before long break
    sessionsBeforeLongBreak: 4,
  },

  /**
   * Data visualization settings
   */
  visualization: {
    // Number of data points to display in real-time chart
    maxDataPoints: 100,

    // Update frequency for biometric display (Hz)
    updateFrequency: 10,

    // Chart colors
    colors: {
      alpha: '#3b82f6',   // Blue - relaxed
      beta: '#22c55e',    // Green - focused
      gamma: '#ef4444',   // Red - stressed
    },
  },

  /**
   * Session logging
   */
  logging: {
    // Enable session data logging to backend
    enabled: true,

    // Log frequency (milliseconds)
    logInterval: 5000,

    // Include canvas snapshots in logs
    includeCanvas: true,
  },

  /**
   * Development/debugging settings
   */
  dev: {
    // Use simulated data instead of real WebSocket
    useSimulatedData: true,

    // Show debug info in console
    debug: true,

    // Simulate EEG data update rate (Hz)
    simulatedUpdateRate: 10,
  },
};

/**
 * Helper function to get current config
 * Use this to access config values throughout the app
 */
export function getConfig() {
  return config;
}

/**
 * Update config values at runtime
 * Example: updateConfig({ intervention: { gammaThreshold: 80 } })
 */
export function updateConfig(updates: Partial<typeof config>) {
  Object.assign(config, updates);
}
