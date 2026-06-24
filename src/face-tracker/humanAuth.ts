import type { Config, Human } from "@vladmandic/human";

const AUTH_CONFIG: Partial<Config> = {
  modelBasePath: "/models/human/",
  backend: "webgl",
  cacheSensitivity: 0,
  face: {
    enabled: true,
    detector: { rotation: true, maxDetected: 1 },
    mesh: { enabled: true },
    iris: { enabled: false },
    attention: { enabled: false },
    emotion: { enabled: false },
    description: { enabled: true },
    antispoof: { enabled: false },
    liveness: { enabled: false },
  },
  body: { enabled: false },
  hand: { enabled: false },
  gesture: { enabled: false },
  segmentation: { enabled: false },
};

let authInstance: Promise<Human> | null = null;

export function getHumanForAuth(): Promise<Human> {
  if (!authInstance) {
    authInstance = import("@vladmandic/human").then(async (mod) => {
      const Ctor = (mod.Human ?? mod.default) as new (config: Partial<Config>) => Human;
      const human = new Ctor(AUTH_CONFIG);
      await human.load();
      await human.warmup();
      return human;
    });
    authInstance.catch(() => {
      authInstance = null;
    });
  }
  return authInstance;
}

/** Normalize facemesh landmarks into a stable embedding when faceres is unavailable. */
function meshEmbedding(mesh: number[][]): number[] {
  const indices = [33, 133, 362, 263, 1, 4, 61, 291, 168, 197, 5, 11];
  const out: number[] = [];
  for (const i of indices) {
    if (mesh[i]) out.push(mesh[i][0], mesh[i][1], mesh[i][2] ?? 0);
  }
  return out;
}

/** Extract face embedding from a video frame for enroll/login. */
export async function captureFaceEmbedding(video: HTMLVideoElement): Promise<number[] | null> {
  const human = await getHumanForAuth();
  const result = await human.detect(video);
  const face = result.face?.[0] as {
    embedding?: number[];
    description?: number[];
    mesh?: number[][];
  } | undefined;
  const vec = face?.embedding ?? face?.description;
  if (vec?.length) return vec.map((x) => Number(x));
  const mesh = face?.mesh as number[][] | undefined;
  if (mesh?.length) {
    const derived = meshEmbedding(mesh);
    return derived.length >= 8 ? derived : null;
  }
  return null;
}
