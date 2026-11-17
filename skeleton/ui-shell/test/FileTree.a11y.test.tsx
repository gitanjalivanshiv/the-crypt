import { fireEvent, render } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it, vi } from "vitest";
import { FileTree } from "../src/components/FileTree";

// Validates: Requirements 6.14
const FILES = ["README.md", "docs/x.md", "src/a.ts", "src/lib/b.ts"];
const item = (path: string) => document.querySelector(`[data-path="${path}"]`) as HTMLElement;
const key = (path: string, k: string) => fireEvent.keyDown(item(path), { key: k });

describe("FileTree keyboard and screen reader (R6.14)", () => {
  it("exposes tree/treeitem roles, aria-expanded and a roving tabindex", () => {
    render(<FileTree files={FILES} cited={[]} />);
    expect(document.querySelector('[role="tree"]')).not.toBeNull();
    const items = document.querySelectorAll('[role="treeitem"]');
    expect(items.length).toBe(3);
    expect(item("docs").getAttribute("aria-expanded")).toBe("false");
    expect(item("README.md").hasAttribute("aria-expanded")).toBe(false);
    const stops = [...items].filter((i) => i.getAttribute("tabindex") === "0");
    expect(stops.length).toBe(1);
  });

  it("ArrowDown/ArrowUp move focus and the tab stop follows", () => {
    render(<FileTree files={FILES} cited={[]} />);
    item("docs").focus();
    key("docs", "ArrowDown");
    expect(document.activeElement).toBe(item("src"));
    expect(item("src").getAttribute("tabindex")).toBe("0");
    expect(item("docs").getAttribute("tabindex")).toBe("-1");
    key("src", "ArrowUp");
    expect(document.activeElement).toBe(item("docs"));
  });

  it("Home and End jump to first and last visible items", () => {
    render(<FileTree files={FILES} cited={[]} />);
    item("docs").focus();
    key("docs", "End");
    expect(document.activeElement).toBe(item("src"));
    key("src", "Home");
    expect(document.activeElement).toBe(item("README.md"));
  });

  it("ArrowRight expands, then moves to first child; ArrowLeft collapses, then moves to parent", () => {
    render(<FileTree files={FILES} cited={[]} />);
    item("src").focus();
    key("src", "ArrowRight");
    expect(item("src").getAttribute("aria-expanded")).toBe("true");
    key("src", "ArrowRight");
    expect(document.activeElement).toBe(item("src/a.ts"));
    key("src/a.ts", "ArrowLeft");
    expect(document.activeElement).toBe(item("src"));
    key("src", "ArrowLeft");
    expect(item("src").getAttribute("aria-expanded")).toBe("false");
  });

  it("Enter selects a file and toggles a directory", () => {
    const onSelect = vi.fn();
    render(<FileTree files={FILES} cited={[]} onSelect={onSelect} />);
    key("README.md", "Enter");
    expect(onSelect).toHaveBeenCalledWith("README.md");
    key("docs", "Enter");
    expect(item("docs").getAttribute("aria-expanded")).toBe("true");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("highlight comes from props only, not from focus or keys", () => {
    const { rerender } = render(<FileTree files={FILES} cited={[]} active="README.md" />);
    item("docs").focus();
    key("docs", "ArrowDown");
    expect(item("README.md").getAttribute("aria-current")).toBe("true");
    expect(item("src").getAttribute("aria-current")).toBeNull();
    rerender(<FileTree files={FILES} cited={[]} active="src" />);
    expect(item("src").getAttribute("aria-current")).toBe("true");
  });

  it("has no axe violations, collapsed or expanded", async () => {
    const { container } = render(<FileTree files={FILES} cited={["src/lib/b.ts"]} active="src/a.ts" />);
    expect((await axe(container)).violations).toEqual([]);
  });
});
