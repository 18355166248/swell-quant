import { describe, expect, it } from "vitest";

import { pageFromPath, pathForPage, resetScrollContainer } from "./App";

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
