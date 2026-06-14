"""
Trading education module — concepts, glossary, and interactive lessons.
"""

from __future__ import annotations
import textwrap

GLOSSARY: dict[str, str] = {
    "Ask": "The lowest price a seller is willing to accept for a security.",
    "Bid": "The highest price a buyer is willing to pay for a security.",
    "Spread": "The difference between the ask and bid prices.",
    "Market Order": "An order to buy/sell immediately at the current best price.",
    "Limit Order": "An order to buy/sell only at a specified price or better.",
    "Stop-Loss": "An order that automatically sells when price drops to a set level, limiting loss.",
    "Take-Profit": "An order that automatically closes a position when price reaches a profit target.",
    "Candlestick": "A price chart showing open, high, low, and close for a time period.",
    "Bullish": "Expecting or experiencing rising prices.",
    "Bearish": "Expecting or experiencing falling prices.",
    "Support": "A price level where buying pressure tends to stop a decline.",
    "Resistance": "A price level where selling pressure tends to stop a rally.",
    "Trend": "The general direction a market is moving (uptrend, downtrend, sideways).",
    "Volume": "The number of shares/units traded in a given period.",
    "Volatility": "The rate at which the price of an asset increases or decreases.",
    "Portfolio": "The collection of investments held by an individual or institution.",
    "Diversification": "Spreading investments across assets to reduce risk.",
    "Leverage": "Using borrowed capital to increase potential return (and risk).",
    "Short Selling": "Borrowing and selling an asset, hoping to buy it back cheaper later.",
    "Long Position": "Buying an asset expecting its price to rise.",
    "Moving Average (MA)": "Average price over N periods, smoothing out price fluctuations.",
    "RSI": "Relative Strength Index — momentum indicator (0-100). >70 overbought, <30 oversold.",
    "MACD": "Moving Average Convergence Divergence — trend-following momentum indicator.",
    "Bollinger Bands": "Bands plotted 2 standard deviations above/below a moving average.",
    "P&L": "Profit and Loss — the net gain or loss on a trade or portfolio.",
    "Drawdown": "The peak-to-trough decline in portfolio value.",
    "Backtesting": "Testing a trading strategy on historical data to evaluate performance.",
    "Paper Trading": "Simulated trading with virtual money to practice without real risk.",
    "Liquidity": "How easily an asset can be bought or sold without affecting its price.",
    "Market Cap": "Total market value of a company's outstanding shares.",
}

LESSONS: list[dict] = [
    {
        "id": 1,
        "title": "What is Trading?",
        "content": """
Trading is the buying and selling of financial instruments — such as stocks,
currencies, commodities, or cryptocurrencies — with the goal of making a profit.

Key points:
  • Traders profit from price differences over time
  • Investing (long-term) vs. Trading (short-term) — both valid approaches
  • Markets operate through supply and demand
  • Risk management is the #1 skill in trading

The two most basic rules:
  1. Never risk more than you can afford to lose
  2. Cut losses short, let profits run
        """,
        "quiz": [
            {
                "q": "What is the primary goal of trading?",
                "options": ["A) Holding assets forever", "B) Profit from price differences", "C) Avoiding taxes", "D) Owning companies"],
                "answer": "B",
            }
        ],
    },
    {
        "id": 2,
        "title": "Reading Price Charts",
        "content": """
Candlestick charts are the most popular way to view price data:

  ┌─ High (shadow/wick)
  │
  ┌─┤  Body = Open to Close
  │ │  Green/White = Close > Open (bullish)
  └─┤  Red/Black  = Close < Open (bearish)
  │
  └─ Low (shadow/wick)

Key chart patterns:
  • Doji      — Open ≈ Close → indecision
  • Hammer    — Small body, long lower wick → potential reversal up
  • Engulfing — Candle body covers previous candle → strong reversal signal

Timeframes:
  1m, 5m, 15m  → Intraday / scalping
  1h, 4h       → Swing trading
  1D, 1W       → Position trading / investing
        """,
        "quiz": [
            {
                "q": "What does a green (bullish) candlestick indicate?",
                "options": ["A) Close < Open", "B) Close > Open", "C) High = Low", "D) No trading"],
                "answer": "B",
            }
        ],
    },
    {
        "id": 3,
        "title": "Technical Indicators",
        "content": """
Technical indicators are mathematical calculations based on price and volume.

Moving Averages (MA):
  • SMA(20) = Average of last 20 closing prices
  • EMA gives more weight to recent prices
  • Golden Cross: 50-MA crosses above 200-MA → bullish signal
  • Death Cross:  50-MA crosses below 200-MA → bearish signal

RSI (Relative Strength Index):
  • Range: 0 to 100
  • Above 70 → Overbought (possible reversal down)
  • Below 30 → Oversold (possible reversal up)
  • Best used in sideways/ranging markets

MACD (Moving Average Convergence Divergence):
  • MACD Line = EMA(12) − EMA(26)
  • Signal Line = EMA(9) of MACD Line
  • Histogram = MACD − Signal
  • Bullish: MACD crosses above Signal
  • Bearish: MACD crosses below Signal

Bollinger Bands:
  • Middle band = SMA(20)
  • Upper/Lower = SMA(20) ± 2 × StdDev
  • Price near upper band → potentially overbought
  • Price near lower band → potentially oversold
        """,
        "quiz": [
            {
                "q": "What RSI value generally indicates an oversold condition?",
                "options": ["A) Above 70", "B) Above 50", "C) Below 30", "D) Below 10"],
                "answer": "C",
            }
        ],
    },
    {
        "id": 4,
        "title": "Risk Management",
        "content": """
Risk management is the most important skill for long-term trading success.

The 1% Rule:
  • Never risk more than 1-2% of your total capital on a single trade
  • Example: $10,000 account → max $100-$200 risk per trade

Position Sizing:
  Risk Amount = Account Size × Risk %
  Position Size = Risk Amount ÷ (Entry Price − Stop-Loss Price)

  Example:
    Account: $10,000 | Risk: 1% = $100
    Entry: $50 | Stop-Loss: $48 → Risk/share = $2
    Position Size = $100 ÷ $2 = 50 shares

Risk:Reward Ratio:
  • Aim for at least 1:2 (risk $1 to potentially make $2)
  • A 1:3 ratio means you can be wrong 70% of the time and still profit

Common mistakes to avoid:
  ✗ Revenge trading after a loss
  ✗ Moving stop-losses to avoid taking a loss
  ✗ Over-leveraging
  ✗ No trading plan
  ✓ Stick to your system, trade the plan
        """,
        "quiz": [
            {
                "q": "Using the 1% rule with a $5,000 account, what is the max risk per trade?",
                "options": ["A) $500", "B) $50", "C) $5", "D) $5,000"],
                "answer": "B",
            }
        ],
    },
    {
        "id": 5,
        "title": "Trading Strategies Overview",
        "content": """
Common trading strategies:

1. Trend Following
   • Buy when price is in an uptrend, sell in a downtrend
   • Tools: Moving averages, MACD, trend lines
   • Best for: Trending markets

2. Mean Reversion
   • Assumes price will return to its average after extremes
   • Tools: Bollinger Bands, RSI, Z-score
   • Best for: Range-bound/sideways markets

3. Breakout Trading
   • Enter when price breaks through key support/resistance
   • Confirms momentum is strong enough to move price significantly
   • Risk: False breakouts (use volume confirmation)

4. Scalping
   • Very short-term trades (seconds to minutes)
   • Small profits, high frequency
   • Requires fast execution and tight spreads

5. Swing Trading
   • Hold positions for days to weeks
   • Capture a "swing" in a trend
   • Lower time commitment than day trading

Our system implements: Moving Average Crossover, RSI Mean Reversion,
and Bollinger Band strategies — see strategies.py
        """,
        "quiz": [
            {
                "q": "Which strategy works best in a trending market?",
                "options": ["A) Mean Reversion", "B) Scalping only", "C) Trend Following", "D) Random entry"],
                "answer": "C",
            }
        ],
    },
]


def show_glossary(term: str | None = None) -> None:
    if term:
        key = next((k for k in GLOSSARY if k.lower() == term.lower()), None)
        if key:
            print(f"\n  {key}:\n    {GLOSSARY[key]}\n")
        else:
            print(f"  Term '{term}' not found. Use learn glossary to see all terms.")
    else:
        print("\n" + "=" * 60)
        print("  TRADING GLOSSARY")
        print("=" * 60)
        for term_key, definition in sorted(GLOSSARY.items()):
            wrapped = textwrap.fill(definition, width=55, subsequent_indent="    ")
            print(f"\n  {term_key}:\n    {wrapped}")
        print()


def show_lesson(lesson_id: int | None = None) -> None:
    if lesson_id is None:
        print("\n" + "=" * 60)
        print("  TRADING LESSONS")
        print("=" * 60)
        for lesson in LESSONS:
            print(f"  Lesson {lesson['id']}: {lesson['title']}")
        print("\n  Run: python -m trading.cli learn lesson <number>")
        print()
        return

    lesson = next((l for l in LESSONS if l["id"] == lesson_id), None)
    if not lesson:
        print(f"  Lesson {lesson_id} not found. Available: 1-{len(LESSONS)}")
        return

    print("\n" + "=" * 60)
    print(f"  LESSON {lesson['id']}: {lesson['title']}")
    print("=" * 60)
    print(lesson["content"])

    print("-" * 60)
    print("  QUIZ")
    print("-" * 60)
    for quiz in lesson["quiz"]:
        print(f"\n  Q: {quiz['q']}")
        for opt in quiz["options"]:
            print(f"     {opt}")
        answer = input("\n  Your answer (A/B/C/D): ").strip().upper()
        if answer == quiz["answer"]:
            print("  ✓ Correct!\n")
        else:
            print(f"  ✗ Incorrect. The answer is {quiz['answer']}.\n")
