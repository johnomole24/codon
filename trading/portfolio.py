"""
Paper-trading portfolio — tracks cash, positions, trade history, and P&L.
Persists state to a JSON file in ~/.codon_trading/.
"""

from __future__ import annotations
import json
import os
import datetime
from pathlib import Path

PORTFOLIO_DIR = Path.home() / ".codon_trading"
PORTFOLIO_FILE = PORTFOLIO_DIR / "portfolio.json"


def _load() -> dict:
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE) as f:
            return json.load(f)
    return {
        "cash": 10_000.0,
        "positions": {},   # symbol -> {shares, avg_price}
        "history": [],
        "created": datetime.datetime.now().isoformat(),
    }


def _save(state: dict) -> None:
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(state, f, indent=2)


class Portfolio:
    def __init__(self):
        self._state = _load()

    @property
    def cash(self) -> float:
        return self._state["cash"]

    @property
    def positions(self) -> dict:
        return self._state["positions"]

    def buy(self, symbol: str, shares: int, price: float) -> dict:
        """Execute a paper buy order."""
        symbol = symbol.upper()
        cost = shares * price
        if cost > self._state["cash"]:
            raise ValueError(
                f"Insufficient cash: need ${cost:,.2f}, have ${self._state['cash']:,.2f}"
            )

        self._state["cash"] -= cost

        pos = self._state["positions"].get(symbol, {"shares": 0, "avg_price": 0.0})
        total_shares = pos["shares"] + shares
        total_cost = pos["shares"] * pos["avg_price"] + cost
        self._state["positions"][symbol] = {
            "shares": total_shares,
            "avg_price": total_cost / total_shares,
        }

        trade = {
            "action": "BUY",
            "symbol": symbol,
            "shares": shares,
            "price": round(price, 4),
            "total": round(cost, 2),
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._state["history"].append(trade)
        _save(self._state)
        return trade

    def sell(self, symbol: str, shares: int, price: float) -> dict:
        """Execute a paper sell order."""
        symbol = symbol.upper()
        pos = self._state["positions"].get(symbol)
        if not pos or pos["shares"] < shares:
            held = pos["shares"] if pos else 0
            raise ValueError(f"Cannot sell {shares} shares of {symbol}: only {held} held")

        proceeds = shares * price
        avg_price = pos["avg_price"]
        pnl = (price - avg_price) * shares
        pnl_pct = (price - avg_price) / avg_price * 100

        pos["shares"] -= shares
        if pos["shares"] == 0:
            del self._state["positions"][symbol]
        else:
            self._state["positions"][symbol] = pos

        self._state["cash"] += proceeds

        trade = {
            "action": "SELL",
            "symbol": symbol,
            "shares": shares,
            "price": round(price, 4),
            "total": round(proceeds, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "avg_buy_price": round(avg_price, 4),
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._state["history"].append(trade)
        _save(self._state)
        return trade

    def reset(self, initial_cash: float = 10_000.0) -> None:
        """Reset portfolio to initial state."""
        self._state = {
            "cash": initial_cash,
            "positions": {},
            "history": [],
            "created": datetime.datetime.now().isoformat(),
        }
        _save(self._state)

    def summary(self, live_prices: dict[str, float] | None = None) -> dict:
        """
        Return portfolio summary.
        live_prices: {symbol: current_price} for mark-to-market.
        """
        positions_value = 0.0
        positions_detail = []

        for symbol, pos in self._state["positions"].items():
            shares = pos["shares"]
            avg_price = pos["avg_price"]
            current_price = (live_prices or {}).get(symbol, avg_price)
            market_value = shares * current_price
            unrealized_pnl = (current_price - avg_price) * shares
            unrealized_pct = (current_price - avg_price) / avg_price * 100

            positions_value += market_value
            positions_detail.append({
                "symbol": symbol,
                "shares": shares,
                "avg_price": round(avg_price, 4),
                "current_price": round(current_price, 4),
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pct": round(unrealized_pct, 2),
            })

        total_value = self._state["cash"] + positions_value
        realized_pnl = sum(t.get("pnl", 0) for t in self._state["history"] if t["action"] == "SELL")

        return {
            "cash": round(self._state["cash"], 2),
            "positions_value": round(positions_value, 2),
            "total_value": round(total_value, 2),
            "realized_pnl": round(realized_pnl, 2),
            "positions": positions_detail,
            "num_trades": len(self._state["history"]),
        }

    def print_summary(self, live_prices: dict[str, float] | None = None) -> None:
        s = self.summary(live_prices)
        print("\n" + "=" * 55)
        print("  PAPER TRADING PORTFOLIO")
        print("=" * 55)
        print(f"  Cash              : ${s['cash']:>12,.2f}")
        print(f"  Positions Value   : ${s['positions_value']:>12,.2f}")
        print(f"  Total Value       : ${s['total_value']:>12,.2f}")
        print(f"  Realized P&L      : ${s['realized_pnl']:>+12,.2f}")
        print(f"  Trades Executed   : {s['num_trades']}")

        if s["positions"]:
            print("\n  Open Positions:")
            print(f"  {'Symbol':<8} {'Shares':>8} {'Avg Price':>12} {'Cur Price':>12} {'Value':>12} {'Unrealized P&L':>16}")
            print("  " + "-" * 72)
            for p in s["positions"]:
                print(
                    f"  {p['symbol']:<8} {p['shares']:>8} "
                    f"${p['avg_price']:>11.4f} ${p['current_price']:>11.4f} "
                    f"${p['market_value']:>11.2f} "
                    f"${p['unrealized_pnl']:>+11.2f} ({p['unrealized_pct']:+.1f}%)"
                )
        else:
            print("\n  No open positions.")
        print()

    def print_history(self, last_n: int = 20) -> None:
        history = self._state["history"][-last_n:]
        if not history:
            print("\n  No trades recorded yet.\n")
            return

        print("\n" + "=" * 75)
        print("  TRADE HISTORY")
        print("=" * 75)
        print(f"  {'Date':<20} {'Action':<6} {'Symbol':<8} {'Shares':>8} {'Price':>12} {'P&L':>12}")
        print("  " + "-" * 70)
        for t in history:
            pnl_str = f"${t['pnl']:+.2f}" if "pnl" in t else ""
            print(
                f"  {t['date']:<20} {t['action']:<6} {t['symbol']:<8} "
                f"{t['shares']:>8} ${t['price']:>11.4f} {pnl_str:>12}"
            )
        print()
