import { describe, expect, it } from "vitest";

import {
  invalidateResearchTaskQueries,
  pageFromPath,
  pathForPage,
  resetScrollContainer,
} from "./App";

describe("app routes", () => {
  it("maps menu pages to stable browser paths", () => {
    expect(pathForPage("dashboard")).toBe("/dashboard");
    expect(pathForPage("predictions")).toBe("/predictions");
    expect(pathForPage("reports")).toBe("/reports");
  });

  it("resolves browser paths back to pages", () => {
    expect(pageFromPath("/")).toBe("dashboard");
    expect(pageFromPath("/dashboard")).toBe("dashboard");
    expect(pageFromPath("/predictions")).toBe("predictions");
    expect(pageFromPath("/predictions/")).toBe("predictions");
    expect(pageFromPath("/unknown")).toBe("dashboard");
  });
});

describe("scroll reset", () => {
  it("uses native scrollTo for content containers", () => {
    const calls: unknown[] = [];
    const container = {
      scrollTop: 320,
      scrollTo: (options: unknown) => calls.push(options),
    };

    resetScrollContainer(container);

    expect(calls).toEqual([{ top: 0, left: 0, behavior: "auto" }]);
  });

  it("falls back to scrollTop when scrollTo is unavailable", () => {
    const container = { scrollTop: 320 };

    resetScrollContainer(container as HTMLElement);

    expect(container.scrollTop).toBe(0);
  });
});

describe("task refresh strategy", () => {
  it("refreshes daily brief and fund trial data after fund trial dry-run", async () => {
    const invalidated: unknown[] = [];
    const queryClient = {
      invalidateQueries: (filters: unknown) => {
        invalidated.push(filters);
        return Promise.resolve();
      },
    };

    await invalidateResearchTaskQueries(queryClient, "fund_trial_dry_run");

    expect(invalidated).toContainEqual({ queryKey: ["daily-brief"] });
    expect(invalidated).toContainEqual({ queryKey: ["fund-trial"] });
    expect(invalidated).toContainEqual({ queryKey: ["funds", "candidates"] });
  });

  it("refreshes daily brief and AKShare trial data after stock trial dry-run", async () => {
    const invalidated: unknown[] = [];
    const queryClient = {
      invalidateQueries: (filters: unknown) => {
        invalidated.push(filters);
        return Promise.resolve();
      },
    };

    await invalidateResearchTaskQueries(queryClient, "akshare_trial_dry_run");

    expect(invalidated).toContainEqual({ queryKey: ["daily-brief"] });
    expect(invalidated).toContainEqual({ queryKey: ["akshare-trial"] });
    expect(invalidated).toContainEqual({ queryKey: ["akshare-universe"] });
  });
});
