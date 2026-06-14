"""
Market data module.

Live data: attempts Yahoo Finance; falls back to simulated data
if the network is unavailable (common in sandboxed environments).

Simulated data uses Geometric Brownian Motion with realistic parameters
seeded from the symbol name — so the same symbol always generates the
same price history.
"""

from __future__ import annotations
import datetime
import hashlib
import numpy as np
import pandas as pd

# Realistic reference prices and volatilities for known symbols
_KNOWN: dict[str, tuple[float, float, float]] = {
    # symbol: (price, annual_vol, annual_drift)
    "AAPL":   (195.0,  0.28, 0.18),
    "MSFT":   (415.0,  0.25, 0.20),
    "GOOGL":  (175.0,  0.30, 0.17),
    "AMZN":   (185.0,  0.32, 0.18),
    "NVDA":   (870.0,  0.55, 0.50),
    "META":   (510.0,  0.38, 0.30),
    "TSLA":   (240.0,  0.65, 0.20),
    "SPY":    (520.0,  0.14, 0.12),
    "QQQ":    (440.0,  0.18, 0.14),
    "BTC-USD": (65000.0, 0.80, 0.40),
    "ETH-USD": (3500.0,  0.90, 0.35),
    "GLD":    (230.0,  0.14, 0.08),
    "NFLX":   (640.0,  0.40, 0.22),
    "COIN":   (220.0,  0.90, 0.30),
}

_PERIOD_DAYS: dict[str, int] = {
    "1d": 1, "5d": 5, "1mo": 21, "3mo": 63, "6mo": 126,
    "1y": 252, "2y": 504, "5y": 1260, "ytd": 126, "max": 1260,
}


def _seed_for(symbol: str) -> int:
    return int(hashlib.md5(symbol.upper().encode()).hexdigest()[:8], 16)


def _simulate_ohlcv(symbol: str, days: int) -> pd.DataFrame:
    """Generate realistic OHLCV data via Geometric Brownian Motion."""
    sym = symbol.upper()
    price0, annual_vol, annual_drift = _KNOWN.get(sym, (100.0, 0.30, 0.10))

    dt = 1 / 252
    rng = np.random.default_rng(_seed_for(sym))

    returns = rng.normal(
        loc=(annual_drift - 0.5 * annual_vol ** 2) * dt,
        scale=annual_vol * np.sqrt(dt),
        size=days,
    )
    closes = price0 * np.exp(np.cumsum(returns))

    # Intraday noise: High/Low around Close
    daily_range = closes * annual_vol * np.sqrt(dt) * rng.uniform(0.5, 2.0, size=days)
    highs = closes + daily_range * rng.uniform(0.3, 0.7, size=days)
    lows = closes - daily_range * rng.uniform(0.3, 0.7, size=days)
    opens = np.roll(closes, 1)
    opens[0] = price0

    avg_vol = 30_000_000 if "BTC" not in sym else 25_000
    volumes = (avg_vol * rng.lognormal(0, 0.5, size=days)).astype(int)

    end = datetime.date.today()
    dates = pd.bdate_range(end=end, periods=days)

    df = pd.DataFrame({
        "Open": opens,
        "High": highs,
        "Low": lows,
        "Close": closes,
        "Volume": volumes,
    }, index=dates)
    df.index.name = "Date"
    return df


def _try_yfinance(symbol: str, period: str, interval: str) -> pd.DataFrame | None:
    import io, contextlib, logging
    try:
        import yfinance as yf
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        ticker = yf.Ticker(symbol)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            df = ticker.history(period=period, interval=interval, timeout=5)
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        return df[["Open", "High", "Low", "Close", "Volume"]].copy()
    except Exception:
        return None


def fetch_ohlcv(
    symbol: str,
    period: str = "3mo",
    interval: str = "1d",
    force_sim: bool = False,
) -> pd.DataFrame:
    """
    Fetch OHLCV data. Tries Yahoo Finance first; falls back to simulation.
    """
    if not force_sim:
        live = _try_yfinance(symbol, period, interval)
        if live is not None:
            return live

    days = _PERIOD_DAYS.get(period, 63)
    return _simulate_ohlcv(symbol, days)


def fetch_quote(symbol: str) -> dict:
    """Return current quote (live or simulated)."""
    # Try live first
    import io, contextlib, logging
    try:
        import yfinance as yf
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            info = yf.Ticker(symbol).fast_info
        price = info.last_price
        prev_close = info.previous_close
        if price and price > 0:
            change = price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close else 0.0
            return {
                "symbol": symbol.upper(),
                "price": round(float(price), 4),
                "change": round(float(change), 4),
                "change_pct": round(float(change_pct), 2),
                "prev_close": round(float(prev_close), 4),
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "live",
            }
    except Exception:
        pass

    # Simulated: use last 2 days of GBM
    df = _simulate_ohlcv(symbol, 2)
    price = float(df["Close"].iloc[-1])
    prev_close = float(df["Close"].iloc[-2])
    change = price - prev_close
    change_pct = (change / prev_close) * 100 if prev_close else 0.0
    return {
        "symbol": symbol.upper(),
        "price": round(price, 4),
        "change": round(change, 4),
        "change_pct": round(change_pct, 2),
        "prev_close": round(prev_close, 4),
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "simulated",
    }


def fetch_multi_quote(symbols: list[str]) -> list[dict]:
    return [fetch_quote(s) for s in symbols]


def print_quote(q: dict) -> None:
    if "error" in q:
        print(f"  {q['symbol']:8s}  ERROR: {q['error']}")
        return
    arrow = "▲" if q["change"] >= 0 else "▼"
    src = f"[{q.get('source','?')}]"
    print(
        f"  {q['symbol']:10s}  ${q['price']:>10.4f}  "
        f"{arrow} {q['change']:+.4f}  "
        f"({q['change_pct']:+.2f}%)  {src}"
    )


def print_ohlcv(df: pd.DataFrame, rows: int = 10) -> None:
    print(f"\n{'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>14}")
    print("-" * 68)
    for ts, row in df.tail(rows).iterrows():
        date_str = str(ts)[:10]
        print(
            f"  {date_str:<10}  {row['Open']:>9.2f}  {row['High']:>9.2f}  "
            f"{row['Low']:>9.2f}  {row['Close']:>9.2f}  {int(row['Volume']):>13,}"
        )
    print()
