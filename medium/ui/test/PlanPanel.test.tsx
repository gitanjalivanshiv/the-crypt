import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { PlanPanel } from "../src/PlanPanel";
import type { AnswerResult, PlanResult } from "../src/types";

const REF = "snap-1";

const answered = (text: string): AnswerResult => ({
  snapshot_id: REF,
  status: "answered",
  claims: [
    {
      kind: "fact",
      text,
      citations: [{ file: "src/pkg/mod.py", line_start: 3, line_end: 9 }],
      figures: [],
    },
  ],
  banishments: [],
  decline_line: null,
  attempts: [],
});

const declined: AnswerResult = {
  snapshot_id: REF,
  status: "declined",
  claims: [],
  banishments: [],
  decline_line: "The spirits are silent on that.",
  attempts: [],
};

const plan: PlanResult = {
  snapshot_id: REF,
  sections: [
    { section: "requirements", result: answered("Requirement one.") },
    { section: "design", result: declined },
    { section: "tasks", result: answered("Task one.") },
  ],
};

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PlanPanel", () => {
  it("posts to the plan route and renders three headed sections, a decline included", async () => {
    const fn = vi.fn(async () => json(200, plan));
    vi.stubGlobal("fetch", fn);
    const user = userEvent.setup();
    const { container } = render(<PlanPanel snapshotRef={REF} licence="MIT" />);

    await user.click(screen.getByRole("button", { name: "Resurrect" }));
    await screen.findByRole("heading", { name: "Requirements" });
    expect(screen.getByRole("heading", { name: "Design" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Tasks" })).toBeTruthy();
    expect(screen.getByText(/Requirement one/)).toBeTruthy();
    expect(screen.getByTestId("decline-line").textContent).toBe("The spirits are silent on that.");

    const calls = fn.mock.calls as unknown as Array<[string, RequestInit]>;
    expect(calls).toHaveLength(1);
    expect(calls[0]![0]).toBe(`/medium/snapshots/${REF}/plan`);
    expect(calls[0]![1].method).toBe("POST");
    expect((await axe(container)).violations).toEqual([]);
  });

  it("shows the structured error and no partial plan", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json(404, { error: { code: "snapshot_not_found", message: "no such snapshot" } }),
      ),
    );
    const user = userEvent.setup();
    render(<PlanPanel snapshotRef={REF} licence="MIT" />);
    await user.click(screen.getByRole("button", { name: "Resurrect" }));
    const region = await screen.findByTestId("plan-error");
    await waitFor(() => expect(region.textContent).toBe("snapshot_not_found: no such snapshot"));
    expect(region.getAttribute("aria-live")).toBe("assertive");
    expect(screen.queryByRole("heading", { name: "Requirements" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Design" })).toBeNull();
  });

  it("ignores a second click while the request is pending", async () => {
    let release: (r: Response) => void = () => {};
    const fn = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          release = resolve;
        }),
    );
    vi.stubGlobal("fetch", fn);
    const user = userEvent.setup();
    render(<PlanPanel snapshotRef={REF} licence="MIT" />);
    const button = screen.getByRole("button", { name: "Resurrect" });
    await user.click(button);
    await user.click(button);
    expect(fn).toHaveBeenCalledTimes(1);
    expect((button as HTMLButtonElement).disabled).toBe(true);
    release(json(200, plan));
    await screen.findByRole("heading", { name: "Tasks" });
  });
});
