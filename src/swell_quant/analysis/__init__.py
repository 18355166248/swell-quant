"""analysis: 单标的的描述性研究（价格坐标）。

只算“事后可算的历史事实”——回撤、趋势、波动、收益分布——供人理解处境、校准预期。
**这些是历史坐标，不是买卖信号**，也不预测未来。
"""

from swell_quant.analysis.prices import describe_prices

__all__ = ["describe_prices"]
