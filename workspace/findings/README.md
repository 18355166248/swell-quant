# findings/ — 已验证结论库

只收**通过三条升级闸门**的结论（样本外 + 双基准 + 样本量，标准见
[docs/research-conventions.md](../../docs/research-conventions.md)）。
一个结论一个文件：`<主题>.md`，须包含：

- 结论一句话 + 证据表（样本外 RankIC/IR/n、对等权全池超额、验证区间）。
- 复现命令（`swell-quant factor ic ...` / `swell-quant backtest ...`）。
- 已知局限与失效条件。
- 来源 research-log 链接。

负结论同样值得沉淀（如"四个简单因子在沪深300 无可信 alpha"，见 README）。

> 仅用于研究，不构成投资建议。
