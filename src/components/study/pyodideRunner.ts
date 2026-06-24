import type { PyodideInterface } from "pyodide";

let pyodidePromise: Promise<PyodideInterface> | null = null;
const loadedPackages = new Set<string>();

const PYODIDE_INDEX =
  "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";

const PACKAGE_IMPORT_RE: Array<{ re: RegExp; pkg: string }> = [
  { re: /\b(import numpy|from numpy)\b/, pkg: "numpy" },
  { re: /\b(import pandas|from pandas)\b/, pkg: "pandas" },
  { re: /\b(import matplotlib|from matplotlib)\b/, pkg: "matplotlib" },
  { re: /\b(import scipy|from scipy)\b/, pkg: "scipy" },
  { re: /\b(import sklearn|from sklearn)\b/, pkg: "scikit-learn" },
  { re: /\b(import sympy|from sympy)\b/, pkg: "sympy" },
];

async function ensurePackages(pyodide: PyodideInterface, source: string): Promise<void> {
  try {
    await pyodide.loadPackagesFromImports(source);
    return;
  } catch {
    /* fall through to explicit package list */
  }
  const needed = PACKAGE_IMPORT_RE.filter(({ re }) => re.test(source)).map(({ pkg }) => pkg);
  const toLoad = needed.filter((pkg) => !loadedPackages.has(pkg));
  if (toLoad.length === 0) return;
  await pyodide.loadPackage(toLoad);
  toLoad.forEach((pkg) => loadedPackages.add(pkg));
}

/** Lazy-load Pyodide once; WASM fetched only on first Run. */
export async function getPyodide(): Promise<PyodideInterface> {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      const { loadPyodide } = await import("pyodide");
      return loadPyodide({ indexURL: PYODIDE_INDEX });
    })();
  }
  return pyodidePromise;
}

export type PythonRunResult = {
  stdout: string;
  stderr: string;
  error: string | null;
};

/** Run Python source in-browser; captures stdout/stderr. */
export async function runPython(source: string): Promise<PythonRunResult> {
  const pyodide = await getPyodide();

  try {
    await ensurePackages(pyodide, source);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { stdout: "", stderr: "", error: `Failed to load Python packages: ${message}` };
  }

  pyodide.runPython(`
import sys
from io import StringIO
sys.stdout = StringIO()
sys.stderr = StringIO()
`);

  try {
    await pyodide.runPythonAsync(source);
    const stdout = pyodide.runPython("sys.stdout.getvalue()") as string;
    const stderr = pyodide.runPython("sys.stderr.getvalue()") as string;
    return { stdout: stdout.trimEnd(), stderr: stderr.trimEnd(), error: null };
  } catch (err) {
    const stdout = pyodide.runPython("sys.stdout.getvalue()") as string;
    const stderr = pyodide.runPython("sys.stderr.getvalue()") as string;
    const message = err instanceof Error ? err.message : String(err);
    return { stdout: stdout.trimEnd(), stderr: stderr.trimEnd(), error: message };
  }
}
