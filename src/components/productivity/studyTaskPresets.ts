import type { StudyTask } from "../../api/plannerClient";

function newId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

export function scalerStudyTask(minutes = 90): StudyTask {
  return {
    id: "scaler-deep-work",
    title: "Scaler / coursework",
    minutes,
    allowHosts: [
      "scaler.com",
      "scaleracademy.com",
      "colab.research.google.com",
      "github.com",
      "stackoverflow.com",
    ],
    blockCategories: [
      "Gaming",
      "Video Streaming",
      "Social Media",
      "Entertainment",
      "Live Streaming",
    ],
  };
}

export function deepReadTask(minutes = 90): StudyTask {
  return {
    id: newId("deep-read"),
    title: "Deep read (notes + PDF)",
    minutes,
    allowHosts: ["localhost", "127.0.0.1", "notion.so", "drive.google.com", "arxiv.org"],
    blockCategories: ["Gaming", "Video Streaming", "Social Media", "Entertainment"],
  };
}

export function dailyReviewTask(minutes = 35): StudyTask {
  return {
    id: "daily-srs-review",
    title: "Daily review (vocab + math + notes)",
    minutes,
    allowHosts: ["localhost", "127.0.0.1"],
    blockCategories: ["Gaming", "Video Streaming", "Social Media", "Entertainment", "Live Streaming"],
  };
}

export function greCycleTask(minutes = 45): StudyTask {
  return {
    id: newId("gre"),
    title: "GRE vocab — Study Loop due queue",
    minutes,
    allowHosts: ["localhost", "127.0.0.1"],
    blockCategories: ["Gaming", "Video Streaming", "Social Media", "Entertainment"],
  };
}

export function adminTask(minutes = 30): StudyTask {
  return {
    id: newId("admin"),
    title: "Admin / email",
    minutes,
    allowHosts: ["mail.google.com", "calendar.google.com", "outlook.com"],
    blockCategories: ["Gaming", "Video Streaming"],
  };
}

export const BLOCK_TEMPLATES: { label: string; tip: string; factory: (minutes?: number) => StudyTask }[] = [
  { label: "Daily SRS", tip: "Study Loop — vocab + math + notes due queue", factory: dailyReviewTask },
  { label: "Scaler block", tip: "Coursework — Scaler + docs only", factory: scalerStudyTask },
  { label: "Deep read", tip: "Notes + PDF — 90m", factory: deepReadTask },
  { label: "GRE / vocab", tip: "Study Loop due queue — 45m", factory: greCycleTask },
  { label: "Admin", tip: "Email + calendar — gate relaxed", factory: adminTask },
];
