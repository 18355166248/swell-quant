import { createElement } from "react";
import { Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import type {
  ArtifactStatus,
  ModelSummary,
  Prediction,
  SettingsArtifact,
  TaskSummary,
} from "../types/api";
import {
  formatDateTime,
  formatFileSize,
  formatNumber,
  statusColor,
} from "./display";

export function buildPredictionColumns(): ColumnsType<Prediction> {
  return [
    { title: "排名", dataIndex: "rank", width: 76, sorter: (a, b) => a.rank - b.rank },
    { title: "代码", dataIndex: "symbol", width: 120 },
    { title: "日期", dataIndex: "date", width: 120 },
    {
      title: "预测分数",
      dataIndex: "score",
      align: "right",
      sorter: (a, b) => a.score - b.score,
      render: (value: number) => value.toFixed(4),
    },
    {
      title: "1 日收益",
      dataIndex: "return_1d",
      align: "right",
      render: formatNumber,
    },
    {
      title: "5 日动量",
      dataIndex: "momentum_5d",
      align: "right",
      render: formatNumber,
    },
    {
      title: "成交量变化",
      dataIndex: "volume_change_1d",
      align: "right",
      render: formatNumber,
    },
  ];
}

interface CheckColumnOptions {
  showKey?: boolean;
  statusLabel?: "localized" | "raw";
  nameWidth?: number;
  statusWidth?: number;
}

interface CheckLike {
  key?: string;
  name: string;
  status: string;
  message: string;
}

export function buildCheckColumns<Row extends CheckLike = CheckLike>(
  options: CheckColumnOptions = {},
): ColumnsType<Row> {
  const statusLabel = options.statusLabel ?? "localized";
  const columns: ColumnsType<Row> = [
    { title: "检查项", dataIndex: "name", width: options.nameWidth },
  ];
  if (options.showKey) {
    columns.push({ title: "Key", dataIndex: "key", width: 210 });
  }
  columns.push(
    {
      title: "状态",
      dataIndex: "status",
      width: options.statusWidth ?? (options.showKey ? 100 : 90),
      render: (value: string) =>
        createElement(
          Tag,
          { color: checkStatusColor(value) },
          statusLabel === "raw" ? value : checkStatusLabel(value),
        ),
    },
    { title: "说明", dataIndex: "message" },
  );
  return columns;
}

interface ArtifactLike {
  name: string;
  path: string;
  size_bytes: number | null;
  updated_at: string | null;
  exists: boolean;
}

type ArtifactRow = ArtifactStatus["artifacts"][number] | SettingsArtifact;

export function buildArtifactColumns<Row extends ArtifactLike = ArtifactRow>({
  missingColor = "red",
}: {
  missingColor?: "red" | "orange";
} = {}): ColumnsType<Row> {
  return [
    { title: "产物", dataIndex: "name", width: 180 },
    { title: "路径", dataIndex: "path" },
    {
      title: "大小",
      dataIndex: "size_bytes",
      align: "right",
      width: 120,
      render: formatFileSize,
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      width: 180,
      render: formatDateTime,
    },
    {
      title: "状态",
      dataIndex: "exists",
      width: missingColor === "orange" ? 120 : 100,
      render: (exists: boolean) =>
        createElement(
          Tag,
          { color: exists ? "green" : missingColor },
          exists ? "存在" : "缺失",
        ),
    },
  ];
}

export function buildTaskSummaryColumns(): ColumnsType<TaskSummary> {
  return [
    { title: "任务", dataIndex: "id" },
    {
      title: "状态",
      dataIndex: "status",
      width: 92,
      render: (status: string) =>
        createElement(Tag, { color: statusColor(status) }, status),
    },
  ];
}

export function buildModelSummaryColumns({
  variant = "detailed",
}: {
  variant?: "compact" | "detailed";
} = {}): ColumnsType<ModelSummary> {
  const columns: ColumnsType<ModelSummary> = [
    { title: "版本", dataIndex: "model_version" },
    { title: "类型", dataIndex: "model_type", width: 130 },
  ];
  if (variant === "detailed") {
    columns.push({ title: "后端", dataIndex: "training_backend", width: 150 });
  }
  columns.push(
    { title: "特征", dataIndex: "feature_count", width: 80, align: "right" },
    { title: "预测日", dataIndex: "prediction_date", width: 120 },
  );
  if (variant === "detailed") {
    columns.push({
      title: "评估",
      dataIndex: "evaluation_status",
      width: 120,
      render: (value: string) =>
        createElement(Tag, { color: value === "ready" ? "green" : "orange" }, value),
    });
  }
  return columns;
}

function checkStatusColor(status: string): string {
  if (status === "passed") {
    return "green";
  }
  if (status === "warning") {
    return "orange";
  }
  return "red";
}

function checkStatusLabel(status: string): string {
  if (status === "passed") {
    return "通过";
  }
  if (status === "warning") {
    return "警告";
  }
  if (status === "failed") {
    return "失败";
  }
  return status;
}
