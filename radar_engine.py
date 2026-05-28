from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf
import yaml


CONFIG_PATH = Path(__file__).with_name("config.yaml")


@dataclass(frozen=True)
class TickerResult:
    symbol: str
    name: str
    group: str
    account: str
    note: str
    price: float
    ma500: float
    deviation: float
    div_yield: float
    pe: float
    market_cap: float
    money_flow: float
    action: str
    comment: str
    error: str = ""


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fmt_large(num: float | int | None) -> str:
    if num is None or pd.isna(num):
        return "-"
    num = float(num)
    a = abs(num)
    if a >= 1e12:
        return f"{num / 1e12:.2f}T"
    if a >= 1e9:
        return f"{num / 1e9:.2f}B"
    if a >= 1e6:
        return f"{num / 1e6:.2f}M"
    return f"{num:.0f}"


def fetch_macro(config: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    values: dict[str, float] = {}
    errors: list[str] = []

    defaults = {
        "^VIX": 18.0,
        "BZ=F": 80.0,
        "GC=F": 2300.0,
        "CAD=X": 1.36,
    }

    for symbol in config["macro"]:
        try:
            hist = yf.Ticker(symbol).history(period="5d", auto_adjust=False)
            if hist.empty:
                raise ValueError("empty history")
            values[symbol] = float(hist["Close"].dropna().iloc[-1])
        except Exception as exc:
            values[symbol] = defaults.get(symbol, 0.0)
            errors.append(f"{symbol}: {exc}")

    return values, errors


def get_action_and_comment(
    symbol: str,
    group: str,
    deviation: float,
    last_close: float,
    macro: dict[str, float],
    config: dict[str, Any],
    meta: dict[str, Any],
) -> tuple[str, str]:
    brent = macro.get("BZ=F", 80.0)
    user_positions = config.get("user_positions", {})

    if symbol in user_positions:
        avg = float(user_positions[symbol]["avg_price"])
        pct = (last_close - avg) / avg * 100
        if last_close < avg:
            return "RESEARCH", f"跌破均价 {avg:.2f}，护甲击穿 {pct:+.1f}%，先复查基本面"
        return "HOLD", f"均价 {avg:.2f} 护甲完好，浮盈 {pct:+.1f}%"

    if symbol == "^VIX":
        if last_close > 35:
            return "BUY_ZONE", "极度恐慌，左侧加仓时刻，先检查清单"
        if last_close > 25:
            return "WATCH", "市场恐慌，准备购物清单"
        if last_close > 18:
            return "WATCH", "情绪偏紧，观察"
        return "HOLD", "情绪稳定"

    if symbol == "BZ=F":
        if last_close > 100:
            return "NO_BUY", "极度滞胀，摧毁估值，ENB 相对受益"
        if last_close > 85:
            return "WATCH", "通胀压力，关注定价权"
        if last_close < 65:
            return "WATCH", "低油价，OXY/周期资产进入观察"
        if last_close < 75:
            return "WATCH", "周期启动信号，OXY 观察名单激活"
        return "HOLD", "油价中性"

    if symbol == "GC=F":
        if deviation > 30:
            return "NO_BUY", "黄金泡沫预警"
        if deviation > 10:
            return "WATCH", "偏贵"
        return "HOLD", "持有/观察"

    if symbol == "CAD=X":
        if last_close > 1.40:
            return "NO_BUY", "汇率极差，严禁换汇"
        if last_close > 1.36:
            return "WATCH", "汇率偏弱，等待"
        if last_close < 1.32:
            return "BUY_ZONE", "优质换汇窗口，可考虑诺伯特套汇"
        return "WATCH", "汇率中性，可小额换汇"

    trigger = meta.get("watch_trigger")
    if trigger:
        trigger_type = trigger.get("type")
        trigger_value = float(trigger.get("value", 0))
        if trigger_type == "ma500_below":
            if deviation <= trigger_value:
                return "RESEARCH", f"观察名单触发，MA500 偏离 {deviation:+.1f}%"
            return "WATCH", f"等待更深回调，当前 MA500 偏离 {deviation:+.1f}%"
        if trigger_type == "brent_below":
            if brent <= trigger_value:
                return "RESEARCH", f"油价触发，Brent 当前 {brent:.1f}"
            return "WATCH", f"等待 Brent < {trigger_value:.0f}，当前 {brent:.1f}"

    if deviation < -20:
        return "BUY_ZONE", "史诗级错杀，分批建仓前先确认护城河完好"
    if deviation < -12:
        return "RESEARCH", "黄金坑，第一批子弹候选，先查财报"
    if deviation < -5:
        return "WATCH", "轻度回调，列入待买清单"
    if deviation < 0:
        return "HOLD", "均线下方，合理区间"
    if deviation < 15:
        return "HOLD", "均线附近，正常持有"
    if deviation < 30:
        return "WATCH", "偏贵区间，不追高"
    if deviation < 50:
        return "NO_BUY", "显著溢价，等待回调"
    return "NO_BUY", "泡沫区，远离或考虑减仓"


def analyze_ticker(
    symbol: str,
    meta: dict[str, Any],
    group: str,
    macro: dict[str, float],
    config: dict[str, Any],
) -> TickerResult:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="10y", auto_adjust=False)
        if hist.empty:
            raise ValueError("empty history")

        hist["MA500"] = hist["Close"].rolling(500).mean()
        last = hist.iloc[-1]
        price = float(last["Close"])
        last_open = float(last["Open"])
        volume = float(last.get("Volume", 0) or 0)
        ma500_raw = hist["MA500"].dropna()
        ma500 = float(ma500_raw.iloc[-1]) if not ma500_raw.empty else 0.0
        deviation = ((price - ma500) / ma500 * 100) if ma500 > 0 else 0.0
        money_flow = (price - last_open) * volume

        div_yield = 0.0
        pe = 0.0
        market_cap = 0.0

        # Yahoo's quoteSummary endpoint is less reliable on Streamlit Cloud,
        # especially for futures, indexes, FX pairs, and some Canadian tickers.
        # Keep the MA500 radar usable even when fundamentals are unavailable.
        if group != "宏观天气台":
            try:
                info = ticker.get_info()
                div_yield = float(info.get("trailingAnnualDividendYield") or 0) * 100
                pe = float(info.get("trailingPE") or 0)
                market_cap = float(info.get("marketCap") or 0)
            except Exception:
                try:
                    fast_info = ticker.fast_info
                    market_cap = float(getattr(fast_info, "market_cap", 0) or 0)
                except Exception:
                    pass

        action, comment = get_action_and_comment(
            symbol=symbol,
            group=group,
            deviation=deviation,
            last_close=price,
            macro=macro,
            config=config,
            meta=meta,
        )

        return TickerResult(
            symbol=symbol,
            name=meta["name"],
            group=group,
            account=meta["account"],
            note=meta.get("note", ""),
            price=price,
            ma500=ma500,
            deviation=deviation,
            div_yield=div_yield,
            pe=pe,
            market_cap=market_cap,
            money_flow=money_flow,
            action=action,
            comment=comment,
        )
    except Exception as exc:
        return TickerResult(
            symbol=symbol,
            name=meta.get("name", symbol),
            group=group,
            account=meta.get("account", "-"),
            note=meta.get("note", ""),
            price=0,
            ma500=0,
            deviation=0,
            div_yield=0,
            pe=0,
            market_cap=0,
            money_flow=0,
            action="ERROR",
            comment="数据获取失败",
            error=str(exc),
        )


def run_scan(config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, float], list[str], str]:
    macro, macro_errors = fetch_macro(config)
    results: list[TickerResult] = []

    for symbol, meta in config["macro"].items():
        results.append(analyze_ticker(symbol, meta, "宏观天气台", macro, config))

    for group, tickers in config["groups"].items():
        for symbol, meta in tickers.items():
            results.append(analyze_ticker(symbol, meta, group, macro, config))

    df = pd.DataFrame([r.__dict__ for r in results])
    scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return df, macro, macro_errors, scanned_at
