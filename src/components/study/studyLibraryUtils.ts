import type { DragEvent } from "react";
import type { LibraryFile, LibraryFolderNode, LibraryTree } from "./StudyLibraryTree";

export function folderOf(relativePath: string): string {
  const parts = relativePath.split("/");
  return parts.length <= 1 ? "" : parts.slice(0, -1).join("/");
}

export function findNodeAt(tree: LibraryTree, folderPath: string): LibraryFolderNode {
  if (!folderPath) return tree.root;
  const parts = folderPath.split("/");
  let node = tree.root;
  let acc = "";
  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : part;
    const next = node.folders.find((f) => f.path === acc);
    if (!next) break;
    node = next;
  }
  return node;
}

export function breadcrumbParts(folderPath: string): { label: string; path: string }[] {
  const crumbs = [{ label: "Study notes", path: "" }];
  if (!folderPath) return crumbs;
  const parts = folderPath.split("/");
  let acc = "";
  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : part;
    crumbs.push({ label: part, path: acc });
  }
  return crumbs;
}

export function collectTopFolders(tree: LibraryTree): LibraryFolderNode[] {
  return tree.root.folders;
}

export function collectAllFiles(node: LibraryFolderNode): LibraryFile[] {
  const out = [...node.files];
  for (const child of node.folders) {
    out.push(...collectAllFiles(child));
  }
  return out;
}

export function findLibraryFile(tree: LibraryTree | null, path: string): LibraryFile | undefined {
  if (!tree) return undefined;
  return collectAllFiles(tree.root).find((f) => f.relative_path === path);
}

export const DRAG_PATH_KEY = "study-library-path";

export function setDragPath(e: DragEvent, path: string) {
  e.dataTransfer.setData("text/plain", path);
  e.dataTransfer.setData(DRAG_PATH_KEY, path);
  e.dataTransfer.effectAllowed = "move";
}

export function getDragPath(e: DragEvent): string {
  return e.dataTransfer.getData(DRAG_PATH_KEY) || e.dataTransfer.getData("text/plain");
}

export function isLibraryDrag(e: DragEvent): boolean {
  return (
    e.dataTransfer.types.includes(DRAG_PATH_KEY) || e.dataTransfer.types.includes("text/plain")
  );
}
