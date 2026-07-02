# 开源参考

## 结论

v1 不直接套用大型量化框架，先自建轻量闭环。原因是第一版目标是验证 A 股日频研究流程，过早接入完整框架会增加环境、数据格式和调试成本。

推荐策略：

- 架构思想参考 Qlib。
- 回测思想参考 vectorbt 和 Backtrader。
- 强化学习路线参考 FinRL，但 v1 不采用。
- 完整交易引擎参考 Lean，但 v1 不采用。

## Qlib

地址：[microsoft/qlib](https://github.com/microsoft/qlib)

定位：AI-oriented quantitative investment platform。

优点：

- 覆盖数据、模型、回测、组合优化等完整 AI 量化链路。
- 适合学习严肃量化平台的模块划分。
- 对 LightGBM、深度模型、研究工作流有成熟示例。

缺点：

- 框架复杂度高。
- 数据格式和工作流有学习成本。
- 第一版如果直接采用，容易被框架约束拖慢 MVP。

v1 决策：不直接采用，参考其数据/模型/回测分层。

## FinRL

地址：[AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL)

定位：面向金融交易的深度强化学习库。

优点：

- 强化学习交易示例丰富。
- 覆盖单股、多股、组合配置等场景。
- 适合后续研究 RL 交易策略。

缺点：

- 强化学习对数据、评估和稳定性要求高。
- 容易在早期引入过多变量。
- v1 的 A 股日频预测不需要 RL。

v1 决策：不采用，作为后续研究参考。

## vectorbt

地址：[polakowo/vectorbt](https://github.com/polakowo/vectorbt)

定位：高性能向量化回测框架。

优点：

- 适合批量测试大量策略和参数。
- pandas/numpy 生态友好。
- 做日频 Top N 和信号回测有参考价值。

缺点：

- 对复杂事件驱动交易限制不如专门交易引擎。
- 第一版自研简单 Top N 回测更容易控制细节。

v1 决策：暂不依赖，回测逻辑成熟后可接入或对照验证。

## Backtrader

地址：[mementum/backtrader](https://github.com/mementum/backtrader)

定位：经典 Python 回测框架。

优点：

- 事件驱动模型成熟。
- 指标、策略、broker 模拟概念完整。
- 适合学习交易约束和回测结构。

缺点：

- 项目风格较老。
- 与现代数据分析栈整合不如轻量自研直接。
- 对第一版研究看板来说偏重。

v1 决策：不采用，参考其策略、broker、analyzer 概念。

## QuantConnect Lean

地址：[QuantConnect/Lean](https://github.com/QuantConnect/Lean)

定位：完整算法交易引擎。

优点：

- 工程完整度高。
- 覆盖多资产、多市场、回测和实盘交易。
- 长期如果做交易系统很有参考价值。

缺点：

- 体系庞大。
- 技术栈和本项目 Python 研究看板路线不完全一致。
- v1 不做实盘交易，用不上完整交易引擎。

v1 决策：不采用，仅作为长期架构参考。

## 选型建议

第一版自建最小闭环：

```txt
AKShare → DuckDB → pandas 因子 → LightGBM → Top N 回测 → React 看板 → LLM 报告
```

当 v1 跑通后再评估：

- 因子和模型变复杂时，引入 Qlib。
- 需要批量参数扫描时，引入 vectorbt。
- 需要事件驱动策略时，引入 Backtrader。
- 需要实盘和多资产执行时，重新评估 Lean 或专门交易系统。
