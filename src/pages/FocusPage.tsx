import FocusControlPanel from "../components/productivity/FocusControlPanel";

/** Web-only Focus control (no PySide6). */
export default function FocusPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <FocusControlPanel />
    </div>
  );
}
