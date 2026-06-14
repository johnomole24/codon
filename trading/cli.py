"""
Command-line interface for the Codon Trading System.

Usage:
  python -m trading.cli <command> [options]

Commands:
  quote   <SYMBOL> [SYMBOL ...]          -- Live price quotes
  chart   <SYMBOL> [--period 3mo]        -- OHLCV price data
  analyze <SYMBOL> [--period 3mo]        -- Technical indicator analysis
  signal  <SYMBOL> --strategy <name>     -- Get current trade signal
  backtest <SYMBOL> --strategy <name>    -- Run strategy backtest
  buy     <SYMBOL> --shares N            -- Paper buy order
  sell    <SYMBOL> [--shares N]          -- Paper sell order (all if omitted)
  portfolio                              -- Show portfolio state
  history                                -- Trade history
  size    --entry P --stop P --account A -- Position size calculator
  learn   [glossary [term] | lesson [N]] -- Trading education

Available strategies: ma_crossover, rsi, bollinger, macd
"""

from __future__ import annotations
import sys
import argparse

from . import data as mkt
from . import indicators as ind
from . import strategies as strat
from . import learn as edu
from .portfolio import Portfolio
from . import executor as ex


def cmd_quote(args):
    symbols = args.symbols
    print(f"\n  Live Quotes  [{mkt.fetch_quote.__module__}]\n")
    quotes = mkt.fetch_multi_quote(symbols)
    for q in quotes:
        mkt.print_quote(q)
    print()


def cmd_chart(args):
    df = mkt.fetch_ohlcv(args.symbol, period=args.period, interval=args.interval)
    print(f"\n  {args.symbol.upper()} — {args.period} OHLCV ({args.interval} bars)")
    mkt.print_ohlcv(df, rows=args.rows)


def cmd_analyze(args):
    df = mkt.fetch_ohlcv(args.symbol, period=args.period)
    df = ind.add_all_indicators(df)
    ind.print_indicator_summary(df)


def cmd_signal(args):
    df = mkt.fetch_ohlcv(args.symbol, period=args.period)
    strategy = strat.get_strategy(args.strategy)
    print(f"\n  Strategy  : {strategy.describe().split(chr(10))[0]}")
    print(f"  Symbol    : {args.symbol.upper()}")
    sig = strat.current_signal(strategy, df)
    print(f"  Signal    : {sig}\n")


def cmd_backtest(args):
    df = mkt.fetch_ohlcv(args.symbol, period=args.period)
    strategy = strat.get_strategy(args.strategy)
    print(f"\n  Symbol    : {args.symbol.upper()}")
    print(f"  Period    : {args.period}\n")
    strategy.backtest(df, initial_capital=args.capital)


def cmd_buy(args):
    portfolio = Portfolio()
    price = args.price if hasattr(args, "price") else None
    if args.stop_loss and args.risk_pct:
        ex.buy(portfolio, args.symbol, price=price,
               risk_pct=args.risk_pct, stop_loss_price=args.stop_loss)
    else:
        if not args.shares:
            print("  Error: specify --shares N (or --risk-pct + --stop-loss for auto-sizing)")
            sys.exit(1)
        ex.buy(portfolio, args.symbol, shares=args.shares, price=price)


def cmd_sell(args):
    portfolio = Portfolio()
    price = args.price if hasattr(args, "price") else None
    ex.sell(portfolio, args.symbol, shares=getattr(args, "shares", None), price=price)


def cmd_portfolio(args):
    portfolio = Portfolio()
    symbols = list(portfolio.positions.keys())
    live_prices = {}
    if symbols:
        for q in mkt.fetch_multi_quote(symbols):
            if "price" in q:
                live_prices[q["symbol"]] = q["price"]
    portfolio.print_summary(live_prices)


def cmd_history(args):
    portfolio = Portfolio()
    portfolio.print_history(last_n=getattr(args, "last", 20))


def cmd_size(args):
    ex.position_size(
        account_size=args.account,
        entry_price=args.entry,
        stop_loss_price=args.stop,
        risk_pct=args.risk_pct,
    )


def cmd_learn(args):
    sub = getattr(args, "learn_cmd", None)
    if sub == "glossary":
        edu.show_glossary(getattr(args, "term", None))
    elif sub == "lesson":
        lesson_id = getattr(args, "lesson_id", None)
        edu.show_lesson(lesson_id)
    else:
        print(__doc__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m trading.cli",
        description="Codon Trading System",
    )
    sub = parser.add_subparsers(dest="command")

    # quote
    p = sub.add_parser("quote", help="Live price quotes")
    p.add_argument("symbols", nargs="+")

    # chart
    p = sub.add_parser("chart", help="OHLCV price chart")
    p.add_argument("symbol")
    p.add_argument("--period", default="3mo")
    p.add_argument("--interval", default="1d")
    p.add_argument("--rows", type=int, default=15)

    # analyze
    p = sub.add_parser("analyze", help="Technical indicator analysis")
    p.add_argument("symbol")
    p.add_argument("--period", default="6mo")

    # signal
    p = sub.add_parser("signal", help="Current trade signal from a strategy")
    p.add_argument("symbol")
    p.add_argument("--strategy", default="ma_crossover",
                   choices=list(strat.STRATEGIES.keys()))
    p.add_argument("--period", default="1y")

    # backtest
    p = sub.add_parser("backtest", help="Backtest a strategy on historical data")
    p.add_argument("symbol")
    p.add_argument("--strategy", default="ma_crossover",
                   choices=list(strat.STRATEGIES.keys()))
    p.add_argument("--period", default="2y")
    p.add_argument("--capital", type=float, default=10_000.0)

    # buy
    p = sub.add_parser("buy", help="Paper buy order")
    p.add_argument("symbol")
    p.add_argument("--shares", type=int)
    p.add_argument("--price", type=float)
    p.add_argument("--risk-pct", dest="risk_pct", type=float, default=1.0)
    p.add_argument("--stop-loss", dest="stop_loss", type=float)

    # sell
    p = sub.add_parser("sell", help="Paper sell order")
    p.add_argument("symbol")
    p.add_argument("--shares", type=int)
    p.add_argument("--price", type=float)

    # portfolio
    sub.add_parser("portfolio", help="Portfolio summary")

    # history
    p = sub.add_parser("history", help="Trade history")
    p.add_argument("--last", type=int, default=20)

    # size (position sizer)
    p = sub.add_parser("size", help="Position size calculator")
    p.add_argument("--entry", type=float, required=True)
    p.add_argument("--stop", type=float, required=True)
    p.add_argument("--account", type=float, default=10_000.0)
    p.add_argument("--risk-pct", dest="risk_pct", type=float, default=1.0)

    # learn
    p = sub.add_parser("learn", help="Trading education")
    learn_sub = p.add_subparsers(dest="learn_cmd")
    g = learn_sub.add_parser("glossary", help="Trading glossary")
    g.add_argument("term", nargs="?", default=None)
    ls = learn_sub.add_parser("lesson", help="Trading lessons")
    ls.add_argument("lesson_id", nargs="?", type=int, default=None)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "quote": cmd_quote,
        "chart": cmd_chart,
        "analyze": cmd_analyze,
        "signal": cmd_signal,
        "backtest": cmd_backtest,
        "buy": cmd_buy,
        "sell": cmd_sell,
        "portfolio": cmd_portfolio,
        "history": cmd_history,
        "size": cmd_size,
        "learn": cmd_learn,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        print(__doc__)
        parser.print_help()


if __name__ == "__main__":
    main()
