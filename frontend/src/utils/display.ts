export function formatPercent(value?: number): string {
  if (value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

export function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : value.toFixed(4);
}

export function formatFileSize(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

export function rejectedTradeReasonLabel(value: string): string {
  const labels: Record<string, string> = {
    missing_next_trade_date: "无下一交易日",
    missing_signal_bar: "缺失信号日行情",
    missing_trade_bar: "缺失成交日行情",
    suspended_or_zero_volume: "停牌或零成交量",
    limit_up_buy_blocked: "涨停买入受限",
  };
  return labels[value] ?? value;
}

export function statusColor(status?: string): string {
  if (status === "success") {
    return "green";
  }
  if (status === "failed") {
    return "red";
  }
  if (status === "busy") {
    return "orange";
  }
  return "default";
}

export function storageStatusColor(status?: string): string {
  if (status === "healthy") {
    return "green";
  }
  if (status === "inconsistent" || status === "schema_mismatch") {
    return "red";
  }
  if (status === "incomplete" || status === "missing") {
    return "orange";
  }
  return "default";
}

export function preflightStatusColor(status?: string): string {
  if (status === "passed") {
    return "green";
  }
  if (status === "warning") {
    return "orange";
  }
  if (status === "failed") {
    return "red";
  }
  return "default";
}
