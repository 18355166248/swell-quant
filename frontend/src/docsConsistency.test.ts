import { describe, expect, it } from "vitest";

import testingDoc from "../../docs/testing.md?raw";

describe("docs/testing.md consistency", () => {
  it("mentions current frontend page and shared component coverage", () => {
    expect(testingDoc).toContain("页面级 render 测试");
    expect(testingDoc).toContain("PageTitle");
    expect(testingDoc).toContain("表格列构造器");
    expect(testingDoc).toContain("设置页不展示 secret 明文");
  });
});
