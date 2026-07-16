---
name: research-factor
description: 按固定 SOP 研究一个因子/策略想法：查口径文档 → 读 preferences → 用 swell-quant CLI 拉数据跑 IC 与双基准回测 → 写 research-log，达标才升 findings。用户说"研究/评估/试一下某因子""跑一下 IC""这个想法有没有 alpha"时使用。
---

# 因子研究 SOP

严格按以下五步执行，不跳步、不改序。

## 1. 查口径

读 `docs/research-conventions.md`，确认数据口径、因子定义、回测口径与
结论评估标准。写策略参数以文档为准，不靠记忆。

## 2. 读偏好

读 `workspace/preferences.md`（硬规则当宪法）：红线、研究纪律、默认参数。
与用户指令冲突时，红线与研究纪律**不可让步**，默认参数可按用户要求调整。

## 3. 拉数据、跑评估

用 CLI（JSON 输出；`--db` 默认 `data/duckdb/marketdata.duckdb`）：

```bash
swell-quant data summary                       # 先确认库内数据覆盖区间
swell-quant factor catalog                     # 可用因子
swell-quant factor ic --name <因子> --start <S> --end <E> [--lookback N | --item X]
swell-quant backtest --factors '[{"name":"...","lookback":N,"weight":1}]' \
  --start <S> --end <E> --benchmark equal_weight
swell-quant backtest --factors '[...]' --start <S> --end <E> \
  --benchmark equal_weight --walk-forward --train-size 24   # 样本外（闸门 1、2 口径）
```

要求：

- IC 与回测都要跑；回测**必须**含等权全池基准（equal_weight）；
  闸门核对用 `--walk-forward`（输出含各因子样本外 RankIC 的 mean/IR/t_stat）。
- 新因子若目录里没有，在 `src/swell_quant/factors/` 按 `Factor` 接口实现
  （只经 as_of 取数），加测试后再评估。
- 每个尝试的参数组合都要留结果，不许只留最好的。

## 4. 写研究日志

按 `workspace/research-log/README.md` 的模板写
`workspace/research-log/YYYY-MM-DD-<主题>.md`：动机、方法、**全部尝试**、
中间观察、下一步。

## 5. 沉淀（有条件）

对照三条闸门（样本外 RankIC、对等权全池正超额、期数 ≥ 30 且跨市场状态）：

- **三条全过** → 摘要写入 `workspace/findings/<主题>.md`（含复现命令与局限）。
- **任一不过** → 留在 research-log，向用户如实报告"未达标"及差在哪条。

输出给用户的总结必须带"仅用于研究，不构成投资建议"，且样本内数字不得
脱离样本外数字单独出现。
