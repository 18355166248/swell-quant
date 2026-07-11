"""factors: 因子层，消费 marketdata（按 as_of 查询，无未来函数）。

每个因子在给定 as_of 与股票池上，产出每只票一个截面因子值（数据不足则 None）。
因子只经 MarketStore 的 as_of 接口取数，天然继承“防未来函数”。
"""

from swell_quant.factors.base import Factor
from swell_quant.factors.momentum import MomentumFactor
from swell_quant.factors.value import ValueFactor

__all__ = ["Factor", "MomentumFactor", "ValueFactor"]
