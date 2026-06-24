import type { PyodideInterface } from "pyodide";

let pyodidePromise: Promise<PyodideInterface> | null = null;

const PYODIDE_INDEX =
  "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";

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
