from __future__ import annotations

from datetime import date
from typing import Any

from swell_quant.research.features import FeatureRow
from swell_quant.research.modeling import PredictionRow


DISCLAIMER = "仅用于研究，不构成投资建议"

FACTOR_LABELS = {
    "momentum_5d": "5日动量",
    "return_1d": "1日收益",
    "volume_change_1d": "成交量变化",
    "rsi_6": "RSI",
    "macd_hist": "MACD",
    "volatility_5d": "5日波动",
}


def build_research_candidates(
    predictions: list[PredictionRow],
    features: list[FeatureRow] | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    if not predictions:
        return {"count": 0, "candidates": [], "disclaimer": DISCLAIMER}

    feature_by_key = {(feature.symbol, feature.trade_date): feature for feature in features or []}
    ordered = sorted(predictions, key=lambda row: (row.rank, row.symbol))[: max(0, top_n)]
    scores = [row.score for row in predictions]
    min_score = min(scores)
    max_score = max(scores)

    candidates = []
    for row in ordered:
        confidence = _confidence(row.score, min_score, max_score)
        confidence_level = _confidence_level(confidence)
        feature = feature_by_key.get((row.symbol, row.trade_date))
        factors = _factor_tags(row, feature)
        risk_hints = _risk_hints(row)
        candidates.append(
            {
                "rank": row.rank,
                "symbol": row.symbol,
                "date": row.trade_date.isoformat(),
                "model_version": row.model_version,
                "score": row.score,
                "confidence": confidence,
                "confidence_level": confidence_level,
                "factors": factors,
                "risk_hints": risk_hints,
                "research_notes": _research_notes(confidence_level, factors, risk_hints),
            }
        )

    return {
        "count": len(candidates),
        "candidates": candidates,
        "disclaimer": DISCLAIMER,
    }


def _confidence(score: float, min_score: float, max_score: float) -> float:
    # 置信度只表示同一批模型分数的相对位置，不是胜率、收益概率或交易信号。
    if max_score == min_score:
        return 0.5
    return round((score - min_score) / (max_score - min_score), 6)


def _confidence_level(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def _factor_tags(row: PredictionRow, feature: FeatureRow | None) -> list[dict[str, Any]]:
    values = {
        "momentum_5d": row.momentum_5d,
        "return_1d": row.return_1d,
        "volume_change_1d": row.volume_change_1d,
        "rsi_6": _normalized_rsi(feature.rsi_6) if feature is not None else None,
        "macd_hist": feature.macd_hist if feature is not None else None,
        "volatility_5d": -feature.volatility_5d
        if feature is not None and feature.volatility_5d is not None
        else None,
    }
    factors = [
        {
            "code": code,
            "name": FACTOR_LABELS[code],
            "value": round(float(value), 6),
            "direction": "up" if float(value) >= 0 else "down",
        }
        for code, value in values.items()
        if value is not None
    ]
    factors.sort(key=lambda item: (-abs(float(item["value"])), str(item["code"])))
    return factors[:3]


def _normalized_rsi(value: float | None) -> float | None:
    if value is None:
        return None
    return (value - 50.0) / 100.0


def _risk_hints(row: PredictionRow) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    # 当前候选阶段还没有逐标的停牌/涨跌停精确字段，先用日收益和成交量异动做显式启发式提示。
    if row.return_1d is not None and abs(row.return_1d) >= 0.095:
        hints.append({"code": "limit_move", "label": "接近涨跌停幅度"})
    if row.volume_change_1d is not None and abs(row.volume_change_1d) >= 2:
        hints.append({"code": "volume_spike", "label": "成交量异动"})
    return hints


def _research_notes(
    confidence_level: str,
    factors: list[dict[str, Any]],
    risk_hints: list[dict[str, str]],
) -> list[str]:
    confidence_text = {
        "high": "高",
        "medium": "中等",
        "low": "低",
    }[confidence_level]
    notes = [f"模型分数在当日候选池中处于{confidence_text}相对位置"]
    positive_factors = [factor["name"] for factor in factors if factor["direction"] == "up"]
    negative_factors = [factor["name"] for factor in factors if factor["direction"] == "down"]
    if positive_factors:
        notes.append(f"主要正向因子：{'、'.join(positive_factors)}")
    if negative_factors:
        notes.append(f"主要负向因子：{'、'.join(negative_factors)}")
    if risk_hints:
        notes.append("已触发风险提示，需先复核交易约束和数据质量")
    else:
        notes.append("未触发启发式风险提示，仍需人工复核数据质量和交易约束")
    return notes


def candidate_date_range(candidates: dict[str, Any]) -> tuple[date | None, date | None]:
    dates = [
        date.fromisoformat(candidate["date"])
        for candidate in candidates.get("candidates", [])
        if candidate.get("date")
    ]
    if not dates:
        return None, None
    return min(dates), max(dates)
