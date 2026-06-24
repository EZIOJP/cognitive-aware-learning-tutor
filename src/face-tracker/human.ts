import type { Config, Human, Result } from "@vladmandic/human";

/**
 * Lazy singleton for @vladmandic/human — face mesh + iris + rotation only.
 * Dynamic import keeps tfjs out of the initial bundle; models load from
 * public/models/human (local-first, no CDN).
 */
const HUMAN_CONFIG: Partial<Config> = {
  modelBasePath: "/models/human/",
  backend: "webgl",
  cacheSensitivity: 0,
  filter: { enabled: true, equalization: false },
  face: {
    enabled: true,
    detector: { rotation: true, maxDetected: 1 },
    mesh: { enabled: true },
    iris: { enabled: true },
    attention: { enabled: false },
    emotion: { enabled: false },
    description: { enabled: false },
    antispoof: { enabled: false },
    liveness: { enabled: false },
  },
  body: { enabled: false },
  hand: { enabled: false },
  gesture: { enabled: false },
  segmentation: { enabled: false },
};

let instance: Promise<Human> | null = null;

export function getHuman(): Promise<Human> {
  if (!instance) {
    instance = import("@vladmandic/human").then(async (mod) => {
      const Ctor = (mod.Human ?? mod.default) as new (config: Partial<Config>) => Human;
      const human = new Ctor(HUMAN_CONFIG);
      await human.load();
      await human.warmup();
      return human;
    });
    instance.catch(() => {
      instance = null;
    });
  }
  return instance;
}

export type { Human, Result };
