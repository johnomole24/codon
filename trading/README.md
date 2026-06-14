# Codon Trading System

A trading **learning** and **paper-execution** platform built on the Codon
repository. Fully self-contained — works offline using a realistic market
simulator (Geometric Brownian Motion) and switches to live Yahoo Finance data
automatically when network access is available.

---

## Quick Start

```bash
# Live/simulated price quotes
python -m trading.cli quote AAPL MSFT BTC-USD NVDA SPY

# OHLCV price chart (last 15 bars)
python -m trading.cli chart AAPL --period 3mo

# Full technical indicator analysis
python -m trading.cli analyze AAPL --period 6mo

# Get a trade signal from a strategy
python -m trading.cli signal AAPL --strategy ma_crossover
python -m trading.cli signal NVDA --strategy rsi

# Backtest a strategy on historical data
python -m trading.cli backtest AAPL --strategy ma_crossover --period 2y
python -m trading.cli backtest SPY  --strategy bollinger   --period 2y
python -m trading.cli backtest TSLA --strategy macd        --period 1y

# Paper trading
python -m trading.cli buy  AAPL --shares 10
python -m trading.cli buy  NVDA --shares 5 --risk-pct 1 --stop-loss 850.00
python -m trading.cli sell AAPL                 # sell all
python -m trading.cli sell NVDA --shares 2      # sell 2 shares
python -m trading.cli portfolio                 # portfolio summary
python -m trading.cli history                   # trade history

# Position size calculator (1% risk rule)
python -m trading.cli size --entry 195.00 --stop 190.00 --account 10000

# Trading education
python -m trading.cli learn lesson          # list all lessons
python -m trading.cli learn lesson 1        # lesson with quiz
python -m trading.cli learn glossary        # full glossary
python -m trading.cli learn glossary RSI    # single term
```

---

## Available Strategies

| Name | Description | Best Market |
|---|---|---|
| `ma_crossover` | Golden/Death Cross (SMA 20/50) | Trending |
| `rsi` | RSI Oversold/Overbought (30/70) | Ranging |
| `bollinger` | Bollinger Band Mean Reversion | Ranging |
| `macd` | MACD Signal Line Crossover | Trending |

---

## Architecture

```
trading/
├── __init__.py      module metadata
├── data.py          market data (live Yahoo Finance + GBM simulator)
├── indicators.py    SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic
├── strategies.py    4 built-in strategies + shared backtest engine
├── portfolio.py     paper-trading portfolio (persisted to ~/.codon_trading/)
├── executor.py      order execution + position size calculator
├── learn.py         5 lessons, 30-term glossary, interactive quizzes
└── cli.py           argparse CLI entry point
```

---

## Technical Indicators

- **SMA / EMA** — Simple and Exponential Moving Averages
- **RSI(14)** — Relative Strength Index (momentum, 0–100)
- **MACD** — Moving Average Convergence Divergence (12/26/9)
- **Bollinger Bands** — 20-period SMA ± 2σ with %B and bandwidth
- **ATR(14)** — Average True Range (volatility)
- **Stochastic %K/%D** — available via `indicators.stochastic()`

---

## Education Module (5 Lessons)

1. What is Trading?
2. Reading Price Charts (candlesticks, timeframes)
3. Technical Indicators (MA, RSI, MACD, Bollinger)
4. Risk Management (1% rule, position sizing, R:R ratio)
5. Trading Strategies Overview

Each lesson includes an interactive quiz.

---

## Notes

- **Paper trading only** — no real money is ever used
- Portfolio state persists to `~/.codon_trading/portfolio.json`
- Simulated prices use GBM seeded from symbol name — deterministic per symbol
- Live data auto-enabled when Yahoo Finance is reachable
