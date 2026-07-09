import { describe, expect, it } from "vitest";

import { pageFromPath, pathForPage } from "./App";

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
