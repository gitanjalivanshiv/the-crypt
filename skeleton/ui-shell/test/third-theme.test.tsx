import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { render, renderHook, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { ChatPanel } from "../src/components/ChatPanel";
import { CrtFrame } from "../src/components/CrtFrame";
import { FileTree } from "../src/components/FileTree";
import { Meter } from "../src/components/Meter";
import { SoundProvider } from "../src/sound/SoundProvider";
import { useSound } from "../src/sound/useSound";
import { contrastRatio } from "../src/theme/contrast";
import { ThemeProvider } from "../src/theme/ThemeProvider";
import { MIN_CONTRAST_RATIO, REQUIRED_PAIRS } from "../src/theme/types";
import type { AnswerResult } from "../src/types";
import { themeC } from "./fixtures/themeC";

// Validates: Requirements 6.10

const result: AnswerResult = {
  snapshot_id: "s1",
  status: "answered",
  claims: [
    {
      kind: "fact",
      text: "Verified fact",
      citations: [{ file: "a.ts", line_start: 1, line_end: 2 }],
      figures: [],
    },
  ],
  banishments: [],
  decline_line: null,
  attempts: [],
};

describe("third theme (data only)", () => {
  it("passes the contrast requirements and effect ranges", () => {
    for (const [fg, bg] of REQUIRED_PAIRS) {
      expect(contrastRatio(themeC.colours[fg], themeC.colours[bg])).toBeGreaterThanOrEqual(
        MIN_CONTRAST_RATIO,
      );
    }
    for (const v of Object.values(themeC.effects)) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
  });

  it("renders every component under the theme", () => {
    const { container } = render(
      <ThemeProvider theme={themeC}>
        <SoundProvider sounds={themeC.sounds}>
          <CrtFrame>
            <FileTree files={["a.ts", "src/b.ts"]} cited={["a.ts"]} />
            <ChatPanel result={result} />
            <Meter value={0.5} label="Level" />
          </CrtFrame>
        </SoundProvider>
      </ThemeProvider>,
    );
    const root = container.querySelector("[data-crypt-theme-root]") as HTMLElement;
    expect(root.style.getPropertyValue("--crypt-colour-bg")).toBe(themeC.colours.bg);
    expect(root.style.getPropertyValue("--crypt-effect-glow")).toBe("0.4");
    expect(screen.getByText(/Verified fact/)).toBeTruthy();
    expect(screen.getByLabelText("Level")).toBeTruthy();
    expect(screen.getByText("a.ts")).toBeTruthy();
  });

  it("exposes sound hooks with the theme's sounds", () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <SoundProvider sounds={themeC.sounds}>{children}</SoundProvider>
    );
    const { result: hook } = renderHook(() => useSound(), { wrapper });
    expect(hook.current.muted).toBe(true);
    expect(() => hook.current.play("send")).not.toThrow();
  });

  it("needs no component edits: no source file references a theme id", () => {
    const dirs = ["../src/components", "../src/sound", "../src/hooks"].map((d) =>
      join(__dirname, d),
    );
    const ids = [themeC.id, "phosphor", "ledger"];
    for (const dir of dirs) {
      for (const f of readdirSync(dir).filter((n) => /\.(tsx?|css)$/.test(n))) {
        const src = readFileSync(join(dir, f), "utf8");
        for (const id of ids) expect(src, `${f} mentions ${id}`).not.toContain(id);
      }
    }
  });
});
