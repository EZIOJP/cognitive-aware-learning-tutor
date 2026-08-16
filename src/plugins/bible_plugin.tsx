import { BookMarked } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { BibleReaderPage } from "../pages/bible/BibleReaderPage";

export const BiblePlugin: PluginDef = {
  id: "bible-reader",
  name: "Bible Reader",
  description: "One chapter a day — mark done for morning unlock.",
  icon: BookMarked,
  isCore: true,
  routes: [{ path: "bible", element: <BibleReaderPage /> }],
  navItems: [{ to: "/bible", label: "Bible", icon: BookMarked, end: true }],
  widgets: [],
};

registerPlugin(BiblePlugin);
