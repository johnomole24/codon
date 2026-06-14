"""
Technical indicators: SMA, EMA, RSI, MACD, Bollinger Bands, ATR.
All functions accept a pandas Series or DataFrame and return a Series.
"""

from __future__ import annotations
import pandas as pd
import numpy as np


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (0–100)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """
    MACD indicator.
    Returns DataFrame with columns: macd, signal, histogram.
    """
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def bollinger_bands(
    series: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> pd.DataFrame:
    """
    Bollinger Bands.
    Returns DataFrame with columns: middle, upper, lower, bandwidth, %b.
    """
    middle = sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    bandwidth = (upper - lower) / middle
    pct_b = (series - lower) / (upper - lower)
    return pd.DataFrame({
        "middle": middle,
        "upper": upper,
        "lower": lower,
        "bandwidth": bandwidth,
        "pct_b": pct_b,
    })


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range — measures volatility.
    df must have High, Low, Close columns.
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def stochastic(
    df: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3,
) -> pd.DataFrame:
    """
    Stochastic Oscillator (%K and %D lines).
    """
    low_min = df["Low"].rolling(window=k_period).min()
    high_max = df["High"].rolling(window=k_period).max()
    pct_k = 100 * (df["Close"] - low_min) / (high_max - low_min)
    pct_d = pct_k.rolling(window=d_period).mean()
    return pd.DataFrame({"pct_k": pct_k, "pct_d": pct_d})


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all common indicators to the OHLCV DataFrame in-place and return it."""
    close = df["Close"]
    df["SMA_20"] = sma(close, 20)
    df["SMA_50"] = sma(close, 50)
    df["EMA_12"] = ema(close, 12)
    df["EMA_26"] = ema(close, 26)
    df["RSI_14"] = rsi(close, 14)

    macd_df = macd(close)
    df["MACD"] = macd_df["macd"]
    df["MACD_Signal"] = macd_df["signal"]
    df["MACD_Hist"] = macd_df["histogram"]

    bb = bollinger_bands(close)
    df["BB_Upper"] = bb["upper"]
    df["BB_Middle"] = bb["middle"]
    df["BB_Lower"] = bb["lower"]
    df["BB_PctB"] = bb["pct_b"]

    df["ATR_14"] = atr(df, 14)

    return df


def print_indicator_summary(df: pd.DataFrame) -> None:
    """Print the latest indicator values in a readable format."""
    row = df.dropna(subset=["RSI_14"]).iloc[-1] if "RSI_14" in df.columns else df.iloc[-1]
    close = row["Close"]

    print("\n" + "=" * 50)
    print("  INDICATOR SUMMARY (latest bar)")
    print("=" * 50)
    print(f"  Price (Close)   : ${close:.4f}")

    if "SMA_20" in df.columns:
        sma20 = row["SMA_20"]
        sma50 = row.get("SMA_50", float("nan"))
        print(f"  SMA(20)         : ${sma20:.4f}  [price {'above' if close > sma20 else 'below'} MA — {'bullish' if close > sma20 else 'bearish'}]")
        if not pd.isna(sma50):
            print(f"  SMA(50)         : ${sma50:.4f}  [price {'above' if close > sma50 else 'below'} MA — {'bullish' if close > sma50 else 'bearish'}]")

    if "RSI_14" in df.columns:
        rsi_val = row["RSI_14"]
        rsi_label = "OVERBOUGHT" if rsi_val > 70 else ("OVERSOLD" if rsi_val < 30 else "neutral")
        print(f"  RSI(14)         : {rsi_val:.1f}  [{rsi_label}]")

    if "MACD" in df.columns:
        macd_val = row["MACD"]
        sig_val = row["MACD_Signal"]
        hist_val = row["MACD_Hist"]
        trend = "BULLISH" if macd_val > sig_val else "BEARISH"
        print(f"  MACD            : {macd_val:.4f}  Signal: {sig_val:.4f}  Hist: {hist_val:+.4f}  [{trend}]")

    if "BB_Upper" in df.columns:
        bb_pct = row["BB_PctB"]
        bb_label = "near upper band" if bb_pct > 0.8 else ("near lower band" if bb_pct < 0.2 else "mid-band")
        print(f"  Bollinger %B    : {bb_pct:.2f}  [{bb_label}]")
        print(f"  BB Upper/Lower  : ${row['BB_Upper']:.4f} / ${row['BB_Lower']:.4f}")

    if "ATR_14" in df.columns:
        print(f"  ATR(14)         : ${row['ATR_14']:.4f}  (daily volatility estimate)")
    print()
