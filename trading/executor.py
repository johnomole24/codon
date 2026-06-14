"""
Trade executor — resolves current price and delegates to the paper portfolio.
Also provides position-size calculation using the 1% risk rule.
"""

from __future__ import annotations
from .portfolio import Portfolio
from .data import fetch_quote


def _get_price(symbol: str, price: float | None) -> float:
    if price is not None:
        return price
    q = fetch_quote(symbol)
    return q["price"]


def buy(
    portfolio: Portfolio,
    symbol: str,
    shares: int | None = None,
    price: float | None = None,
    risk_pct: float | None = None,
    stop_loss_price: float | None = None,
) -> dict:
    """
    Buy shares.  Two modes:
      1. shares specified → buy that many shares at current (or given) price
      2. risk_pct + stop_loss_price → auto-size position using 1% rule
    """
    current_price = _get_price(symbol, price)

    if shares is None:
        if risk_pct is None or stop_loss_price is None:
            raise ValueError("Provide either 'shares' or both 'risk_pct' and 'stop_loss_price'")
        risk_amount = portfolio.cash * (risk_pct / 100)
        risk_per_share = abs(current_price - stop_loss_price)
        if risk_per_share <= 0:
            raise ValueError("stop_loss_price must be below current price for a long trade")
        shares = max(1, int(risk_amount / risk_per_share))

    trade = portfolio.buy(symbol, shares, current_price)
    print(f"\n  ✓ BUY  {shares} × {symbol} @ ${current_price:.4f}  = ${trade['total']:,.2f}")
    print(f"    Remaining cash: ${portfolio.cash:,.2f}\n")
    return trade


def sell(
    portfolio: Portfolio,
    symbol: str,
    shares: int | None = None,
    price: float | None = None,
) -> dict:
    """
    Sell shares.  If shares is None, sells entire position.
    """
    current_price = _get_price(symbol, price)

    if shares is None:
        pos = portfolio.positions.get(symbol.upper())
        if not pos:
            raise ValueError(f"No open position in {symbol}")
        shares = pos["shares"]

    trade = portfolio.sell(symbol, shares, current_price)
    pnl_str = f"${trade['pnl']:+.2f} ({trade['pnl_pct']:+.1f}%)"
    print(f"\n  ✓ SELL {shares} × {symbol} @ ${current_price:.4f}  P&L: {pnl_str}")
    print(f"    Cash now: ${portfolio.cash:,.2f}\n")
    return trade


def position_size(
    account_size: float,
    entry_price: float,
    stop_loss_price: float,
    risk_pct: float = 1.0,
) -> dict:
    """
    Calculate position size using the fixed-risk (1%) rule.
    Returns a dict with recommended shares and dollar amounts.
    """
    risk_amount = account_size * (risk_pct / 100)
    risk_per_share = abs(entry_price - stop_loss_price)
    shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
    position_cost = shares * entry_price
    potential_loss = shares * risk_per_share
    reward_target = entry_price + 2 * (entry_price - stop_loss_price)

    result = {
        "account_size": account_size,
        "risk_pct": risk_pct,
        "risk_amount": round(risk_amount, 2),
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
        "risk_per_share": round(risk_per_share, 4),
        "recommended_shares": shares,
        "position_cost": round(position_cost, 2),
        "potential_loss": round(potential_loss, 2),
        "reward_target_1r2r": round(reward_target, 4),
    }

    print("\n" + "=" * 50)
    print("  POSITION SIZE CALCULATOR")
    print("=" * 50)
    print(f"  Account Size      : ${account_size:>12,.2f}")
    print(f"  Risk %            : {risk_pct}%")
    print(f"  Risk Amount       : ${risk_amount:>12,.2f}")
    print(f"  Entry Price       : ${entry_price:>12.4f}")
    print(f"  Stop-Loss         : ${stop_loss_price:>12.4f}")
    print(f"  Risk per Share    : ${risk_per_share:>12.4f}")
    print(f"  Recommended Shares: {shares:>12}")
    print(f"  Position Cost     : ${position_cost:>12,.2f}")
    print(f"  Max Loss (if SL)  : ${potential_loss:>12,.2f}")
    print(f"  1:2 Reward Target : ${reward_target:>12.4f}")
    print()
    return result
