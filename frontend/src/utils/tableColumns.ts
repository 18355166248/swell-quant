import type { ColumnsType } from "antd/es/table";
import type { Prediction } from "../types/api";
import { formatNumber } from "./display";

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
