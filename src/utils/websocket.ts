/**
 * WebSocket utilities for connecting to FastAPI backend
 *
 * Usage:
 * ```typescript
 * const eegClient = new EEGWebSocketClient('ws://localhost:8000/ws/eeg');
 *
 * eegClient.onData((data) => {
 *   console.log('Received EEG data:', data);
 *   setBiometricData(prev => [...prev, data]);
 * });
 *
 * eegClient.onConnectionChange((connected) => {
 *   setIsConnected(connected);
 * });
 *
 * eegClient.connect();
 * ```
 */

import { BiometricData } from '../types';

export class EEGWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 2000; // ms
  private dataCallback: ((data: BiometricData) => void) | null = null;
  private connectionCallback: ((connected: boolean) => void) | null = null;
  private errorCallback: ((error: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
  }

  /**
   * Connect to WebSocket server
   */
  public connect(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.warn('WebSocket already connected');
      return;
    }

    try {
      this.ws = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      this.handleReconnect();
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  public disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Register callback for incoming EEG data
   */
  public onData(callback: (data: BiometricData) => void): void {
    this.dataCallback = callback;
  }

  /**
   * Register callback for connection status changes
   */
  public onConnectionChange(callback: (connected: boolean) => void): void {
    this.connectionCallback = callback;
  }

  /**
   * Register callback for errors
   */
  public onError(callback: (error: Event) => void): void {
    this.errorCallback = callback;
  }

  /**
   * Check if currently connected
   */
  public isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('✓ WebSocket connected to EEG stream');
      this.reconnectAttempts = 0;
      this.connectionCallback?.(true);
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const biometricData: BiometricData = {
          alpha: data.alpha,
          beta: data.beta,
          gamma: data.gamma,
          timestamp: data.timestamp,
        };
        this.dataCallback?.(biometricData);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.errorCallback?.(error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket closed');
      this.connectionCallback?.(false);
      this.handleReconnect();
    };
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached. Giving up.');
      return;
    }

    this.reconnectAttempts++;
    console.log(
      `Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`
    );

    setTimeout(() => {
      this.connect();
    }, this.reconnectDelay * this.reconnectAttempts); // Exponential backoff
  }
}

/**
 * Request AI intervention from backend
 */
export async function requestAIIntervention(
  canvasImage: string,
  biometricData: BiometricData,
  backendUrl: string = 'http://localhost:8000'
): Promise<{
  intervention: string;
  question: string;
  detected_concept: string;
  confidence: number;
}> {
  try {
    const response = await fetch(`${backendUrl}/api/intervention`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        canvas_image: canvasImage,
        biometric_data: {
          alpha: biometricData.alpha,
          beta: biometricData.beta,
          gamma: biometricData.gamma,
          timestamp: biometricData.timestamp,
        },
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return {
      intervention: data.intervention,
      question: data.question,
      detected_concept: data.detected_concept,
      confidence: data.confidence || 0.85,
    };
  } catch (error) {
    console.error('Failed to request AI intervention:', error);

    // Return fallback intervention
    return {
      intervention: 'I noticed your cognitive load increased significantly.',
      question: 'Would you like me to break down the problem into smaller steps?',
      detected_concept: 'General Problem Solving',
      confidence: 0.3,
    };
  }
}

/**
 * Log session data to backend
 */
export async function logSessionData(
  sessionData: any,
  backendUrl: string = 'http://localhost:8000'
): Promise<void> {
  try {
    await fetch(`${backendUrl}/api/log-session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(sessionData),
    });
  } catch (error) {
    console.error('Failed to log session data:', error);
  }
}

/**
 * Calculate cognitive load from biometric data
 */
export function calculateCognitiveLoad(
  alpha: number,
  beta: number,
  gamma: number
): 'low' | 'medium' | 'high' {
  // Simple threshold-based approach
  if (gamma > 60) return 'high';
  if (gamma > 35) return 'medium';
  return 'low';

  // Alternative: Weighted formula
  // const cognitiveScore = (gamma * 0.6) + (beta * 0.3) - (alpha * 0.1);
  // if (cognitiveScore > 50) return 'high';
  // if (cognitiveScore > 25) return 'medium';
  // return 'low';
}

/**
 * Detect if intervention should be triggered
 */
export function shouldTriggerIntervention(
  gamma: number,
  timeSinceLastCanvasUpdate: number,
  gammaThreshold: number = 70,
  inactivityThreshold: number = 45
): boolean {
  return gamma > gammaThreshold && timeSinceLastCanvasUpdate > inactivityThreshold;
}
