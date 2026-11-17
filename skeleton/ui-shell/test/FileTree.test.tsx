import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FileTree } from "../src/components/FileTree";

const FILES = ["README.md", "src/a.ts", "src/lib/b.ts", "src/lib/deep/c.ts", "docs/x.md"];

const item = (path: string) => document.querySelector(`[data-path="${path}"]`) as HTMLElement | null;

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FileTree", () => {
  it("shows only top level entries when nothing is cited", () => {
    render(<FileTree files={FILES} cited={[]} />);
    expect(item("src")).not.toBeNull();
    expect(item("src/a.ts")).toBeNull();
    expect(item("src")?.getAttribute("aria-expanded")).toBe("false");
  });

  it("expands the ancestors of a cited file and marks it", () => {
    render(<FileTree files={FILES} cited={["src/lib/deep/c.ts"]} />);
    for (const dir of ["src", "src/lib", "src/lib/deep"]) {
      expect(item(dir)?.getAttribute("aria-expanded")).toBe("true");
    }
    expect(item("src/lib/deep/c.ts")?.getAttribute("data-cited")).toBe("true");
    expect(item("src/lib/b.ts")?.getAttribute("data-cited")).toBeNull();
    expect(item("docs")?.getAttribute("aria-expanded")).toBe("false");
  });

  it("ignores collapse of a cited ancestor", () => {
    render(<FileTree files={FILES} cited={["src/lib/b.ts"]} />);
    fireEvent.click(screen.getByText("src"));
    fireEvent.keyDown(item("src")!, { key: "ArrowLeft" });
    expect(item("src")?.getAttribute("aria-expanded")).toBe("true");
    expect(item("src/lib/b.ts")).not.toBeNull();
  });

  it("lets the user toggle an uncited directory", () => {
    render(<FileTree files={FILES} cited={[]} />);
    fireEvent.click(screen.getByText("docs"));
    expect(item("docs/x.md")).not.toBeNull();
    fireEvent.click(screen.getByText("docs"));
    expect(item("docs/x.md")).toBeNull();
  });

  it("updates the highlight when cited changes", () => {
    const { rerender } = render(<FileTree files={FILES} cited={["src/a.ts"]} />);
    expect(item("src/a.ts")?.getAttribute("data-cited")).toBe("true");
    rerender(<FileTree files={FILES} cited={["docs/x.md"]} />);
    expect(item("docs/x.md")?.getAttribute("data-cited")).toBe("true");
    // The previously cited file is no longer forced visible, and carries no mark.
    expect(item("src/a.ts")).toBeNull();
  });

  it("scrolls the active item into view", () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    render(<FileTree files={FILES} cited={["src/a.ts"]} active="src/a.ts" />);
    expect(scroll).toHaveBeenCalledWith({ block: "nearest" });
    expect(item("src/a.ts")?.getAttribute("aria-current")).toBe("true");
  });

  it("supports keyboard navigation and selection", () => {
    const onSelect = vi.fn();
    render(<FileTree files={FILES} cited={[]} onSelect={onSelect} />);
    const first = item("README.md")!;
    // Order is sorted by path: "README.md" < "docs" < "src" (uppercase first).
    first.focus();
    fireEvent.keyDown(first, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("README.md");
    fireEvent.keyDown(first, { key: "End" });
    expect(document.activeElement).toBe(item("src"));
    fireEvent.keyDown(item("src")!, { key: "ArrowRight" });
    expect(item("src")?.getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(item("src")!, { key: "ArrowRight" });
    expect(document.activeElement).toBe(item("src/a.ts"));
    fireEvent.keyDown(item("src/a.ts")!, { key: "ArrowLeft" });
    expect(document.activeElement).toBe(item("src"));
    fireEvent.keyDown(item("src")!, { key: "ArrowLeft" });
    expect(item("src")?.getAttribute("aria-expanded")).toBe("false");

  });

  it("has tree roles and no accessibility violations", async () => {
    const { container } = render(<FileTree files={FILES} cited={["src/a.ts"]} />);
    expect(screen.getByRole("tree")).toBeTruthy();
    expect(screen.getAllByRole("treeitem").length).toBeGreaterThan(0);
    expect((await axe(container)).violations).toEqual([]);
  });
});
