"""
Alpaca Markets broker integration for live / paper trading.

Set environment variables before starting the server:
  ALPACA_KEY    — Alpaca API key (from alpaca.markets dashboard)
  ALPACA_SECRET — Alpaca API secret
  ALPACA_PAPER  — "true" (default) for paper trading, "false" for live money
"""
from __future__ import annotations
import os


def is_configured() -> bool:
    return bool(os.environ.get("ALPACA_KEY")) and bool(os.environ.get("ALPACA_SECRET"))


def _paper() -> bool:
    return os.environ.get("ALPACA_PAPER", "true").lower() != "false"


def _client():
    from alpaca.trading.client import TradingClient
    key = os.environ.get("ALPACA_KEY", "")
    secret = os.environ.get("ALPACA_SECRET", "")
    if not key or not secret:
        raise RuntimeError("ALPACA_KEY and ALPACA_SECRET env vars are not set")
    return TradingClient(key, secret, paper=_paper())


def get_account() -> dict:
    c = _client()
    a = c.get_account()
    return {
        "id": str(a.id),
        "status": str(a.status),
        "cash": float(a.cash),
        "portfolio_value": float(a.portfolio_value),
        "equity": float(a.equity),
        "buying_power": float(a.buying_power),
        "paper": _paper(),
    }


def place_order(symbol: str, side: str, qty: float | None = None, notional: float | None = None) -> dict:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    c = _client()
    req = MarketOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        notional=notional if not qty else None,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    order = c.submit_order(req)
    return {
        "id": str(order.id),
        "symbol": order.symbol,
        "side": str(order.side.value) if hasattr(order.side, "value") else str(order.side),
        "qty": str(order.qty),
        "status": str(order.status.value) if hasattr(order.status, "value") else str(order.status),
        "submitted_at": str(order.submitted_at),
    }


def get_positions() -> list:
    c = _client()
    return [
        {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry": float(p.avg_entry_price),
            "current_price": float(p.current_price),
            "market_value": float(p.market_value),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_plpc": round(float(p.unrealized_plpc) * 100, 2),
        }
        for p in c.get_all_positions()
    ]
