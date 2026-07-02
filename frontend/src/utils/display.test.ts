import { describe, expect, it } from "vitest";

import {
  formatDateTime,
  formatFileSize,
  formatNumber,
  formatPercent,
  preflightStatusColor,
  rejectedTradeReasonLabel,
  statusColor,
  storageStatusColor,
} from "./display";

describe("display utilities", () => {
  it("formats nullable numeric research values for compact tables", () => {
    expect(formatPercent(0.12345)).toBe("12.35%");
    expect(formatPercent(undefined)).toBe("-");
    expect(formatPercent(Number.NaN)).toBe("-");
    expect(formatNumber(1.23456)).toBe("1.2346");
    expect(formatNumber(null)).toBe("-");
  });

  it("formats artifact sizes and timestamps for status pages", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(2048)).toBe("2.0 KB");
    expect(formatFileSize(2 * 1024 * 1024)).toBe("2.0 MB");
    expect(formatFileSize(null)).toBe("-");
    expect(formatDateTime(null)).toBe("-");
  });

  it("maps backend status values to Ant Design tag colors", () => {
    expect(statusColor("success")).toBe("green");
    expect(statusColor("failed")).toBe("red");
    expect(statusColor("busy")).toBe("orange");
    expect(storageStatusColor("healthy")).toBe("green");
    expect(storageStatusColor("schema_mismatch")).toBe("red");
    expect(storageStatusColor("missing")).toBe("orange");
    expect(preflightStatusColor("passed")).toBe("green");
    expect(preflightStatusColor("warning")).toBe("orange");
    expect(preflightStatusColor("failed")).toBe("red");
  });

  it("keeps trade rejection reasons readable without hiding unknown backend values", () => {
    expect(rejectedTradeReasonLabel("limit_up_buy_blocked")).toBe("涨停买入受限");
    expect(rejectedTradeReasonLabel("new_backend_reason")).toBe("new_backend_reason");
  });
});
