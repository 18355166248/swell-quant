import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PageTitle } from "./PageTitle";

describe("PageTitle", () => {
  it("renders page heading, description, and optional action content", () => {
    const html = renderToStaticMarkup(
      <PageTitle
        title="研究工作台"
        description="查看离线研究链路。"
        extra={<span>刷新</span>}
      />,
    );

    expect(html).toContain('class="page-title"');
    expect(html).toContain("研究工作台");
    expect(html).toContain("查看离线研究链路。");
    expect(html).toContain("刷新");
  });
});
