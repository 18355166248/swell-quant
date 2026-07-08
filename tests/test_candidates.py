from datetime import date

from swell_quant.research.candidates import build_research_candidates
from swell_quant.research.features import FeatureRow
from swell_quant.research.modeling import PredictionRow


def prediction(symbol: str, rank: int, score: float) -> PredictionRow:
    return PredictionRow(
        symbol=symbol,
        trade_date=date(2024, 1, 31),
        model_version="baseline-rule-v1",
        score=score,
        rank=rank,
        return_1d=0.096 if symbol == "000001.SZ" else 0.01,
        momentum_5d=0.08 if symbol == "000001.SZ" else -0.02,
        volume_change_1d=2.4 if symbol == "000001.SZ" else 0.2,
    )


def feature(symbol: str) -> FeatureRow:
    return FeatureRow(
        symbol=symbol,
        trade_date=date(2024, 1, 31),
        close=10.0,
        return_1d=0.096,
        momentum_5d=0.08,
        ma_5=9.8,
        volatility_5d=0.03,
        rsi_6=74.0,
        macd_dif=0.2,
        macd_signal=0.1,
        macd_hist=0.1,
        volume_change_1d=2.4,
    )


def test_build_research_candidates_returns_ranked_research_context() -> None:
    rows = [
        prediction("000002.SZ", 2, 0.4),
        prediction("000001.SZ", 1, 0.9),
        prediction("600000.SH", 3, 0.1),
    ]

    payload = build_research_candidates(rows, features=[feature("000001.SZ")], top_n=2)

    assert payload["count"] == 2
    assert payload["disclaimer"] == "仅用于研究，不构成投资建议"
    assert payload["candidates"][0]["symbol"] == "000001.SZ"
    assert payload["candidates"][0]["confidence"] == 1.0
    assert payload["candidates"][0]["confidence_level"] == "high"
    assert payload["candidates"][0]["factors"][0] == {
        "code": "volume_change_1d",
        "name": "成交量变化",
        "value": 2.4,
        "direction": "up",
    }
    assert {hint["code"] for hint in payload["candidates"][0]["risk_hints"]} == {
        "limit_move",
        "volume_spike",
    }
    assert payload["candidates"][0]["research_notes"] == [
        "模型分数在当日候选池中处于高相对位置",
        "主要正向因子：成交量变化、RSI、MACD",
        "已触发风险提示，需先复核交易约束和数据质量",
    ]


def test_build_research_candidates_handles_flat_scores_and_empty_rows() -> None:
    rows = [prediction("000001.SZ", 1, 0.2), prediction("000002.SZ", 2, 0.2)]

    payload = build_research_candidates(rows)

    assert [candidate["confidence"] for candidate in payload["candidates"]] == [0.5, 0.5]
    assert [candidate["confidence_level"] for candidate in payload["candidates"]] == [
        "medium",
        "medium",
    ]
    assert build_research_candidates([]) == {
        "count": 0,
        "candidates": [],
        "disclaimer": "仅用于研究，不构成投资建议",
    }
