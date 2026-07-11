from datetime import date

import pytest

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.factors.momentum import MomentumFactor
from swell_quant.marketdata.records import BarRecord
from swell_quant.marketdata.store import MarketStore
from swell_quant.portfolio.walkforward import train_ic_weights, walk_forward_backtest


def _bar(symbol, day, close):
    return BarRecord(
        symbol=symbol, date=date(2026, 1, day), open=close, high=close, low=close,
        close=close, volume=100, amount=close * 100, adj_factor=1.0, source="test",
    )


# 5 只票几何增长，日收益率各异 → 未来收益严格有序。
RATES = {"a": 0.00, "b": 0.005, "c": 0.01, "d": 0.015, "e": 0.02}
SYMBOLS = list(RATES)


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    for sym, rate in RATES.items():
        s.write_bars([_bar(sym, d, 10.0 * (1 + rate) ** d) for d in range(1, 15)])
    yield s
    s.close()


class FakeFactor(Factor):
    def __init__(self, values, name="fake"):
        self._values = values
        self._name = name

    @property
    def name(self):
        return self._name

    def compute(self, store, symbols, as_of) -> FactorValues:
        return {s: self._values.get(s) for s in symbols}


# ---- train_ic_weights ----

def test_weight_positive_when_factor_predicts(store):
    # 因子打分与增长（未来收益）同序 → 训练 RankIC=+1 → 权重 ≈ +1。
    factor = FakeFactor({"a": 1, "b": 2, "c": 3, "d": 4, "e": 5})
    [fw] = train_ic_weights([factor], store, SYMBOLS, [date(2026, 1, 1), date(2026, 1, 3)], horizon=2)
    assert fw.weight == pytest.approx(1.0)


def test_weight_negative_when_factor_anti_predicts(store):
    # 反向打分 → 训练 RankIC=-1 → 权重 ≈ -1（方向自校正）。
    factor = FakeFactor({"a": 5, "b": 4, "c": 3, "d": 2, "e": 1})
    [fw] = train_ic_weights([factor], store, SYMBOLS, [date(2026, 1, 1), date(2026, 1, 3)], horizon=2)
    assert fw.weight == pytest.approx(-1.0)


def test_weight_zero_when_no_dispersion(store):
    # 因子对所有票同值 → IC 无定义 → 权重 0。
    factor = FakeFactor({s: 1.0 for s in SYMBOLS})
    [fw] = train_ic_weights([factor], store, SYMBOLS, [date(2026, 1, 1), date(2026, 1, 3)], horizon=2)
    assert fw.weight == 0.0


def test_momentum_trains_positive_weight(store):
    # 真实动量因子在持续增长的数据上应训练出正权重。
    [fw] = train_ic_weights([MomentumFactor(2)], store, SYMBOLS, [date(2026, 1, 5), date(2026, 1, 7)], horizon=2)
    assert fw.weight > 0


# ---- walk_forward_backtest ----

def test_walk_forward_produces_oos_periods(store):
    dates = [date(2026, 1, d) for d in (1, 3, 5, 7, 9, 11)]
    result = walk_forward_backtest(
        [MomentumFactor(2)], store, SYMBOLS, dates, train_size=2, top_n=1, horizon=2
    )
    # 前 train_size 期用于训练，不产生持仓。
    assert len(result.periods) == len(dates) - 2
    assert result.periods[0].as_of == date(2026, 1, 5)


def test_walk_forward_selects_winner_out_of_sample(store):
    # 动量在训练期学到 e（增长最快）最优 → 样本外持续买 e、收益为正。
    dates = [date(2026, 1, d) for d in (1, 3, 5, 7, 9, 11)]
    result = walk_forward_backtest(
        [MomentumFactor(2)], store, SYMBOLS, dates, train_size=2, top_n=1, horizon=2
    )
    assert result.total_return is not None
    assert result.total_return > 0
    assert all(p.ret is not None and p.ret > 0 for p in result.periods)


def test_anti_factor_weight_still_selects_winner(store):
    # 反向因子经 IC 加权（负权重）后，样本外仍应选出真正的赢家 e。
    dates = [date(2026, 1, d) for d in (1, 3, 5, 7, 9, 11)]
    anti = FakeFactor({"a": 5, "b": 4, "c": 3, "d": 2, "e": 1})  # 与真实收益反向
    result = walk_forward_backtest([anti], store, SYMBOLS, dates, train_size=2, top_n=1, horizon=2)
    # 负 IC → 负权重 → -anti 使 e 得分最高 → 样本外收益为正。
    assert result.total_return > 0
