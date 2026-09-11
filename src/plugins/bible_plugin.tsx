import { BookMarked } from "lucide-react";
import { Navigate } from "react-router";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { BibleReaderPage } from "../pages/bible/BibleReaderPage";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";

function BibleRoute() {
  if (!isFocusDesktopShell()) {
    return <Navigate to="/" replace />;
  }
  return <BibleReaderPage />;
}

export const BiblePlugin: PluginDef = {
  id: "bible-reader",
  name: "Bible Reader",
  description: "One chapter a day — mark done for morning unlock.",
  icon: BookMarked,
  isCore: true,
  routes: [{ path: "bible", element: <BibleRoute /> }],
  navItems: [],
  widgets: [],
};

registerPlugin(BiblePlugin);
