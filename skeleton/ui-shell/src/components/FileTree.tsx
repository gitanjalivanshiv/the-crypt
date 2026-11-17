/// <reference types="vite/client" />
import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import styles from "./FileTree.module.css";

export interface FileTreeProps {
  files: string[];
  cited: readonly string[];
  active?: string;
  onSelect?: (path: string) => void;
}

interface Node {
  name: string;
  path: string;
  isDir: boolean;
  children: Node[];
}

/** Every proper directory prefix of a path: "a/b/c.ts" -> ["a", "a/b"]. */
function ancestors(path: string): string[] {
  const parts = path.split("/");
  const out: string[] = [];
  for (let i = 1; i < parts.length; i++) out.push(parts.slice(0, i).join("/"));
  return out;
}

function buildTree(files: string[]): Node[] {
  const root: Node = { name: "", path: "", isDir: true, children: [] };
  const dirs = new Map<string, Node>([["", root]]);
  for (const file of [...new Set(files)].sort()) {
    let parent = root;
    for (const dir of ancestors(file)) {
      let node = dirs.get(dir);
      if (!node) {
        node = { name: dir.slice(dir.lastIndexOf("/") + 1), path: dir, isDir: true, children: [] };
        dirs.set(dir, node);
        parent.children.push(node);
      }
      parent = node;
    }
    parent.children.push({
      name: file.slice(file.lastIndexOf("/") + 1),
      path: file,
      isDir: false,
      children: [],
    });
  }
  return root.children;
}

/**
 * Collapsible file tree. Expansion is derived as `userExpanded ∪ ancestors(cited)`,
 * so a cited file is always visible. Highlight is driven by props only.
 */
export function FileTree({ files, cited, active, onSelect }: FileTreeProps) {
  const tree = useMemo(() => buildTree(files), [files]);
  const [userExpanded, setUserExpanded] = useState<ReadonlySet<string>>(new Set());
  const [focused, setFocused] = useState<string | null>(null);
  const items = useRef(new Map<string, HTMLElement>());

  const citedSet = useMemo(() => new Set(cited), [cited]);
  const forced = useMemo(() => new Set(cited.flatMap(ancestors)), [cited]);
  const isExpanded = (path: string) => forced.has(path) || userExpanded.has(path);

  const visible = useMemo(() => {
    const out: Node[] = [];
    const walk = (nodes: Node[]) => {
      for (const n of nodes) {
        out.push(n);
        if (n.isDir && (forced.has(n.path) || userExpanded.has(n.path))) walk(n.children);
      }
    };
    walk(tree);
    return out;
  }, [tree, forced, userExpanded]);

  const parentOf = (path: string) => ancestors(path).at(-1);
  const tabStop =
    visible.find((n) => n.path === focused)?.path ??
    visible.find((n) => n.path === active)?.path ??
    visible[0]?.path;

  useEffect(() => {
    if (active) items.current.get(active)?.scrollIntoView?.({ block: "nearest" });
  }, [active, visible]);

  const toggle = (path: string) => {
    if (forced.has(path)) return; // cited ancestors cannot be collapsed
    setUserExpanded((prev) => {
      const next = new Set(prev);
      if (!next.delete(path)) next.add(path);
      return next;
    });
  };

  const moveTo = (path: string | undefined) => {
    if (path === undefined) return;
    setFocused(path);
    items.current.get(path)?.focus();
  };

  const activate = (node: Node) => {
    if (node.isDir) toggle(node.path);
    else onSelect?.(node.path);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLElement>, node: Node) => {
    if (e.target !== e.currentTarget) return;
    const idx = visible.findIndex((n) => n.path === node.path);
    switch (e.key) {
      case "ArrowDown":
        moveTo(visible[idx + 1]?.path);
        break;
      case "ArrowUp":
        moveTo(visible[idx - 1]?.path);
        break;
      case "Home":
        moveTo(visible[0]?.path);
        break;
      case "End":
        moveTo(visible.at(-1)?.path);
        break;
      case "ArrowRight":
        if (!node.isDir) return;
        if (!isExpanded(node.path)) toggle(node.path);
        else moveTo(node.children[0]?.path);
        break;
      case "ArrowLeft":
        if (node.isDir && isExpanded(node.path) && !forced.has(node.path)) toggle(node.path);
        else moveTo(parentOf(node.path));
        break;
      case "Enter":
      case " ":
        activate(node);
        break;
      default:
        return;
    }
    e.preventDefault();
    e.stopPropagation();
  };

  const renderNodes = (nodes: Node[]) =>
    nodes.map((node) => {
      const expanded = node.isDir ? isExpanded(node.path) : undefined;
      const isCited = citedSet.has(node.path);
      const classes = [styles.row, isCited && styles.cited, node.path === active && styles.active]
        .filter(Boolean)
        .join(" ");
      return (
        <li
          key={node.path}
          role="treeitem"
          aria-expanded={expanded}
          aria-current={node.path === active ? "true" : undefined}
          aria-selected={node.path === active}
          tabIndex={node.path === tabStop ? 0 : -1}
          data-path={node.path}
          data-cited={isCited ? "true" : undefined}
          className={styles.item}
          ref={(el) => {
            if (el) items.current.set(node.path, el);
            else items.current.delete(node.path);
          }}
          onKeyDown={(e) => onKeyDown(e, node)}
          onFocus={(e) => {
            if (e.target === e.currentTarget) setFocused(node.path);
          }}
        >
          <div
            className={classes}
            onClick={(e) => {
              e.stopPropagation();
              setFocused(node.path);
              activate(node);
            }}
          >
            <span aria-hidden="true" className={styles.marker}>
              {node.isDir ? (expanded ? "▾" : "▸") : " "}
            </span>
            <span>{node.name}</span>
            {isCited && <span className={styles.srOnly}> (cited)</span>}
          </div>
          {node.isDir && expanded && node.children.length > 0 && (
            <ul role="group" className={styles.group}>
              {renderNodes(node.children)}
            </ul>
          )}
        </li>
      );
    });

  return (
    <ul role="tree" aria-label="Files" className={styles.tree}>
      {renderNodes(tree)}
    </ul>
  );
}
