"""
Trading strategies. Each strategy exposes:
  - generate_signals(df) -> pd.DataFrame  (adds 'signal' column: 1=BUY, -1=SELL, 0=HOLD)
  - backtest(df)         -> dict           (performance metrics)
  - describe()           -> str
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from . import indicators as ind


# ──────────────────────────────────────────────────────
# Shared backtest engine
# ──────────────────────────────────────────────────────

def _run_backtest(df: pd.DataFrame, initial_capital: float = 10_000.0) -> dict:
    """
    Simulate trading on a DataFrame that has a 'signal' column.
    Returns performance metrics dict.
    """
    df = df.copy().dropna(subset=["signal"])
    capital = initial_capital
    position = 0          # shares held
    entry_price = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = [capital]

    for i, (ts, row) in enumerate(df.iterrows()):
        price = row["Close"]
        signal = int(row["signal"])

        if signal == 1 and position == 0:          # BUY
            position = int(capital // price)
            entry_price = price
            capital -= position * price
            trades.append({"type": "BUY", "date": str(ts)[:10], "price": price, "shares": position})

        elif signal == -1 and position > 0:         # SELL
            proceeds = position * price
            capital += proceeds
            pnl = (price - entry_price) * position
            trades.append({
                "type": "SELL",
                "date": str(ts)[:10],
                "price": price,
                "shares": position,
                "pnl": round(pnl, 2),
            })
            position = 0
            entry_price = 0.0

        portfolio_value = capital + position * price
        equity_curve.append(portfolio_value)

    # Close any open position at last price
    if position > 0:
        last_price = df["Close"].iloc[-1]
        capital += position * last_price
        pnl = (last_price - entry_price) * position
        trades.append({
            "type": "CLOSE (open pos)",
            "date": str(df.index[-1])[:10],
            "price": last_price,
            "shares": position,
            "pnl": round(pnl, 2),
        })

    final_value = capital
    total_return = (final_value - initial_capital) / initial_capital * 100

    # Buy-and-hold benchmark
    bh_shares = int(initial_capital // df["Close"].iloc[0])
    bh_value = bh_shares * df["Close"].iloc[-1] + (initial_capital - bh_shares * df["Close"].iloc[0])
    bh_return = (bh_value - initial_capital) / initial_capital * 100

    # Drawdown
    eq = pd.Series(equity_curve)
    rolling_max = eq.cummax()
    drawdown = (eq - rolling_max) / rolling_max * 100
    max_drawdown = float(drawdown.min())

    closed_trades = [t for t in trades if "pnl" in t]
    winning = [t for t in closed_trades if t["pnl"] > 0]
    win_rate = len(winning) / len(closed_trades) * 100 if closed_trades else 0

    return {
        "initial_capital": initial_capital,
        "final_value": round(final_value, 2),
        "total_return_pct": round(total_return, 2),
        "buy_hold_return_pct": round(bh_return, 2),
        "num_trades": len(closed_trades),
        "win_rate_pct": round(win_rate, 1),
        "max_drawdown_pct": round(max_drawdown, 2),
        "trades": trades,
    }


def _print_backtest_results(results: dict, strategy_name: str) -> None:
    print("\n" + "=" * 55)
    print(f"  BACKTEST: {strategy_name}")
    print("=" * 55)
    print(f"  Initial Capital   : ${results['initial_capital']:,.2f}")
    print(f"  Final Value       : ${results['final_value']:,.2f}")
    print(f"  Strategy Return   : {results['total_return_pct']:+.2f}%")
    print(f"  Buy & Hold Return : {results['buy_hold_return_pct']:+.2f}%")
    print(f"  Num Trades        : {results['num_trades']}")
    print(f"  Win Rate          : {results['win_rate_pct']:.1f}%")
    print(f"  Max Drawdown      : {results['max_drawdown_pct']:.2f}%")
    outperform = results["total_return_pct"] - results["buy_hold_return_pct"]
    print(f"  Alpha (vs B&H)    : {outperform:+.2f}%")
    print()

    if results["trades"]:
        print("  Recent Trades:")
        print(f"  {'Type':<20} {'Date':<12} {'Price':>10} {'Shares':>8} {'P&L':>10}")
        print("  " + "-" * 63)
        for t in results["trades"][-10:]:
            pnl_str = f"${t['pnl']:+.2f}" if "pnl" in t else ""
            print(f"  {t['type']:<20} {t['date']:<12} ${t['price']:>9.2f} {t['shares']:>8}  {pnl_str:>9}")
    print()


# ──────────────────────────────────────────────────────
# Strategy 1: Moving Average Crossover
# ──────────────────────────────────────────────────────

class MACrossover:
    """
    Golden/Death Cross strategy.
    BUY  when fast MA crosses above slow MA (golden cross).
    SELL when fast MA crosses below slow MA (death cross).
    """

    def __init__(self, fast: int = 20, slow: int = 50):
        self.fast = fast
        self.slow = slow

    def describe(self) -> str:
        return (
            f"Moving Average Crossover (fast={self.fast}, slow={self.slow})\n"
            f"  BUY  signal: SMA({self.fast}) crosses above SMA({self.slow}) — Golden Cross\n"
            f"  SELL signal: SMA({self.fast}) crosses below SMA({self.slow}) — Death Cross\n"
            f"  Best for: Trending markets. Lags by nature — confirms after the move."
        )

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["fast_ma"] = ind.sma(df["Close"], self.fast)
        df["slow_ma"] = ind.sma(df["Close"], self.slow)
        df["signal"] = 0
        cross_up = (df["fast_ma"] > df["slow_ma"]) & (df["fast_ma"].shift(1) <= df["slow_ma"].shift(1))
        cross_dn = (df["fast_ma"] < df["slow_ma"]) & (df["fast_ma"].shift(1) >= df["slow_ma"].shift(1))
        df.loc[cross_up, "signal"] = 1
        df.loc[cross_dn, "signal"] = -1
        return df

    def backtest(self, df: pd.DataFrame, initial_capital: float = 10_000.0) -> dict:
        df_sig = self.generate_signals(df)
        results = _run_backtest(df_sig, initial_capital)
        _print_backtest_results(results, self.describe().split("\n")[0])
        return results


# ──────────────────────────────────────────────────────
# Strategy 2: RSI Mean Reversion
# ──────────────────────────────────────────────────────

class RSIMeanReversion:
    """
    RSI oversold/overbought mean-reversion strategy.
    BUY  when RSI < oversold threshold.
    SELL when RSI > overbought threshold.
    """

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def describe(self) -> str:
        return (
            f"RSI Mean Reversion (period={self.period}, OS={self.oversold}, OB={self.overbought})\n"
            f"  BUY  signal: RSI drops below {self.oversold} (oversold)\n"
            f"  SELL signal: RSI rises above {self.overbought} (overbought)\n"
            f"  Best for: Range-bound / sideways markets."
        )

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["RSI"] = ind.rsi(df["Close"], self.period)
        df["signal"] = 0
        buy_cond = (df["RSI"] < self.oversold) & (df["RSI"].shift(1) >= self.oversold)
        sell_cond = (df["RSI"] > self.overbought) & (df["RSI"].shift(1) <= self.overbought)
        df.loc[buy_cond, "signal"] = 1
        df.loc[sell_cond, "signal"] = -1
        return df

    def backtest(self, df: pd.DataFrame, initial_capital: float = 10_000.0) -> dict:
        df_sig = self.generate_signals(df)
        results = _run_backtest(df_sig, initial_capital)
        _print_backtest_results(results, self.describe().split("\n")[0])
        return results


# ──────────────────────────────────────────────────────
# Strategy 3: Bollinger Band Breakout
# ──────────────────────────────────────────────────────

class BollingerBandStrategy:
    """
    Bollinger Band mean-reversion strategy.
    BUY  when price closes below lower band (oversold squeeze).
    SELL when price closes above middle band (mean reversion target).
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev

    def describe(self) -> str:
        return (
            f"Bollinger Band Mean Reversion (period={self.period}, std={self.std_dev})\n"
            f"  BUY  signal: Price closes below lower band\n"
            f"  SELL signal: Price closes above middle band (SMA)\n"
            f"  Best for: Mean-reverting assets with relatively stable volatility."
        )

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        bb = ind.bollinger_bands(df["Close"], self.period, self.std_dev)
        df["BB_Upper"] = bb["upper"]
        df["BB_Middle"] = bb["middle"]
        df["BB_Lower"] = bb["lower"]
        df["signal"] = 0
        buy_cond = df["Close"] < df["BB_Lower"]
        sell_cond = df["Close"] > df["BB_Middle"]
        df.loc[buy_cond, "signal"] = 1
        df.loc[sell_cond, "signal"] = -1
        return df

    def backtest(self, df: pd.DataFrame, initial_capital: float = 10_000.0) -> dict:
        df_sig = self.generate_signals(df)
        results = _run_backtest(df_sig, initial_capital)
        _print_backtest_results(results, self.describe().split("\n")[0])
        return results


# ──────────────────────────────────────────────────────
# Strategy 4: MACD Signal Line Crossover
# ──────────────────────────────────────────────────────

class MACDStrategy:
    """
    MACD line crosses above/below signal line.
    BUY  when MACD crosses above signal line.
    SELL when MACD crosses below signal line.
    """

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def describe(self) -> str:
        return (
            f"MACD Crossover (fast={self.fast}, slow={self.slow}, signal={self.signal})\n"
            f"  BUY  signal: MACD line crosses above signal line\n"
            f"  SELL signal: MACD line crosses below signal line\n"
            f"  Best for: Trending markets with clear momentum shifts."
        )

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        macd_df = ind.macd(df["Close"], self.fast, self.slow, self.signal)
        df["MACD"] = macd_df["macd"]
        df["MACD_Signal"] = macd_df["signal"]
        df["signal"] = 0
        cross_up = (df["MACD"] > df["MACD_Signal"]) & (df["MACD"].shift(1) <= df["MACD_Signal"].shift(1))
        cross_dn = (df["MACD"] < df["MACD_Signal"]) & (df["MACD"].shift(1) >= df["MACD_Signal"].shift(1))
        df.loc[cross_up, "signal"] = 1
        df.loc[cross_dn, "signal"] = -1
        return df

    def backtest(self, df: pd.DataFrame, initial_capital: float = 10_000.0) -> dict:
        df_sig = self.generate_signals(df)
        results = _run_backtest(df_sig, initial_capital)
        _print_backtest_results(results, self.describe().split("\n")[0])
        return results


STRATEGIES: dict[str, type] = {
    "ma_crossover": MACrossover,
    "rsi": RSIMeanReversion,
    "bollinger": BollingerBandStrategy,
    "macd": MACDStrategy,
}


def get_strategy(name: str, **kwargs):
    cls = STRATEGIES.get(name.lower())
    if not cls:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(STRATEGIES.keys())}")
    return cls(**kwargs)


def current_signal(strategy, df: pd.DataFrame) -> str:
    """Return the latest signal from a strategy as a human-readable string."""
    df_sig = strategy.generate_signals(df)
    last_signals = df_sig["signal"].replace(0, pd.NA).dropna()
    if last_signals.empty:
        return "HOLD (no signal generated)"
    last_val = int(last_signals.iloc[-1])
    last_date = str(last_signals.index[-1])[:10]
    if last_val == 1:
        return f"BUY  (last signal on {last_date})"
    elif last_val == -1:
        return f"SELL (last signal on {last_date})"
    return "HOLD"
