"""
Flask REST API for the Codon Trading mobile PWA.

Endpoints:
  GET  /api/quote/<symbol>
  GET  /api/chart/<symbol>?period=3mo&interval=1d
  GET  /api/analyze/<symbol>?period=6mo
  GET  /api/signal/<symbol>?strategy=ma_crossover&period=1y
  POST /api/backtest  {symbol, strategy, period, capital}
  GET  /api/portfolio
  POST /api/trade/buy   {symbol, shares?, risk_pct?, stop_loss?}
  POST /api/trade/sell  {symbol, shares?}
  POST /api/portfolio/reset
  GET  /api/learn/lessons
  GET  /api/learn/lesson/<id>
  GET  /api/learn/glossary
  POST /api/size  {entry, stop, account, risk_pct}
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from flask import Flask, jsonify, request, send_from_directory, redirect, abort
import pandas as pd
import numpy as np

from trading import data as mkt
from trading import indicators as ind
from trading import strategies as strat
from trading import learn as edu
from trading.portfolio import Portfolio
from trading import executor as ex

app = Flask(__name__, static_folder="static", static_url_path="")

# ── Auth + DB setup ───────────────────────────────────────────────────────────
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-in-production-32char")

from trading.app.db import db, User, WalletTransaction, init_db
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

init_db(app)

login_manager = LoginManager(app)

@login_manager.user_loader
def _load_user(uid):
    return User.query.get(int(uid))

@login_manager.unauthorized_handler
def _unauth():
    return jsonify({"error": "Authentication required"}), 401

def _uid():
    return current_user.id if current_user.is_authenticated else None

def _admin_required(f):
    from functools import wraps
    @wraps(f)
    def _wrap(*a, **kw):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*a, **kw)
    return _wrap

# ── Static / PWA ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/manifest.json")
def manifest():
    return send_from_directory(app.static_folder, "manifest.json")

@app.route("/sw.js")
def sw():
    return send_from_directory(app.static_folder, "sw.js")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _df_to_records(df: pd.DataFrame) -> list[dict]:
    df = df.copy()
    df.index = df.index.astype(str).str[:10]
    return df.reset_index().rename(columns={"index": "date", "Date": "date"}).to_dict(orient="records")

def _safe_float(v):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), 6)


# ── Market Data ───────────────────────────────────────────────────────────────

@app.get("/api/quote/<symbol>")
def api_quote(symbol):
    try:
        q = mkt.fetch_quote(symbol)
        return jsonify(q)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/quote-multi")
def api_quote_multi():
    symbols = request.args.get("symbols", "AAPL,MSFT,NVDA,SPY,BTC-USD").split(",")
    return jsonify(mkt.fetch_multi_quote([s.strip() for s in symbols]))


@app.get("/api/chart/<symbol>")
def api_chart(symbol):
    period = request.args.get("period", "3mo")
    interval = request.args.get("interval", "1d")
    try:
        df = mkt.fetch_ohlcv(symbol, period=period, interval=interval)
        return jsonify(_df_to_records(df))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ── Analysis ──────────────────────────────────────────────────────────────────

@app.get("/api/analyze/<symbol>")
def api_analyze(symbol):
    period = request.args.get("period", "6mo")
    try:
        df = mkt.fetch_ohlcv(symbol, period=period)
        df = ind.add_all_indicators(df)
        row = df.dropna(subset=["RSI_14"]).iloc[-1]
        return jsonify({
            "symbol": symbol.upper(),
            "period": period,
            "close": _safe_float(row["Close"]),
            "sma20": _safe_float(row.get("SMA_20")),
            "sma50": _safe_float(row.get("SMA_50")),
            "ema12": _safe_float(row.get("EMA_12")),
            "rsi14": _safe_float(row.get("RSI_14")),
            "macd": _safe_float(row.get("MACD")),
            "macd_signal": _safe_float(row.get("MACD_Signal")),
            "macd_hist": _safe_float(row.get("MACD_Hist")),
            "bb_upper": _safe_float(row.get("BB_Upper")),
            "bb_middle": _safe_float(row.get("BB_Middle")),
            "bb_lower": _safe_float(row.get("BB_Lower")),
            "bb_pct_b": _safe_float(row.get("BB_PctB")),
            "atr14": _safe_float(row.get("ATR_14")),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/signal/<symbol>")
def api_signal(symbol):
    strategy_name = request.args.get("strategy", "ma_crossover")
    period = request.args.get("period", "1y")
    try:
        df = mkt.fetch_ohlcv(symbol, period=period)
        strategy = strat.get_strategy(strategy_name)
        sig = strat.current_signal(strategy, df)
        return jsonify({
            "symbol": symbol.upper(),
            "strategy": strategy_name,
            "signal": sig,
            "description": strategy.describe(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/backtest")
def api_backtest():
    body = request.get_json() or {}
    symbol = body.get("symbol", "AAPL")
    strategy_name = body.get("strategy", "ma_crossover")
    period = body.get("period", "2y")
    capital = float(body.get("capital", 10_000))
    try:
        df = mkt.fetch_ohlcv(symbol, period=period)
        strategy = strat.get_strategy(strategy_name)
        df_sig = strategy.generate_signals(df)
        from trading.strategies import _run_backtest
        results = _run_backtest(df_sig, capital)
        results.pop("trades", None)   # keep response small; trades sent separately
        trades_raw = _run_backtest(strategy.generate_signals(df), capital).get("trades", [])
        results["trades"] = trades_raw[-20:]
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ── Portfolio & Trading ────────────────────────────────────────────────────────

@app.get("/api/portfolio")
def api_portfolio():
    try:
        portfolio = Portfolio(_uid())
        symbols = list(portfolio.positions.keys())
        live_prices = {}
        if symbols:
            for q in mkt.fetch_multi_quote(symbols):
                if "price" in q:
                    live_prices[q["symbol"]] = q["price"]
        s = portfolio.summary(live_prices)
        s["history"] = portfolio._state["history"][-30:]
        return jsonify(s)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/trade/buy")
def api_buy():
    body = request.get_json() or {}
    symbol = body.get("symbol", "")
    shares = body.get("shares")
    price = body.get("price")
    risk_pct = float(body.get("risk_pct", 1.0))
    stop_loss = body.get("stop_loss")
    try:
        portfolio = Portfolio(_uid())
        trade = ex.buy(
            portfolio, symbol,
            shares=int(shares) if shares else None,
            price=float(price) if price else None,
            risk_pct=risk_pct if not shares else None,
            stop_loss_price=float(stop_loss) if stop_loss and not shares else None,
        )
        return jsonify({"success": True, "trade": trade, "cash": portfolio.cash})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/trade/sell")
def api_sell():
    body = request.get_json() or {}
    symbol = body.get("symbol", "")
    shares = body.get("shares")
    price = body.get("price")
    try:
        portfolio = Portfolio(_uid())
        trade = ex.sell(
            portfolio, symbol,
            shares=int(shares) if shares else None,
            price=float(price) if price else None,
        )
        return jsonify({"success": True, "trade": trade, "cash": portfolio.cash})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/portfolio/reset")
def api_reset():
    try:
        capital = float((request.get_json() or {}).get("capital", 10_000))
        Portfolio(_uid()).reset(capital)
        return jsonify({"success": True, "cash": capital})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/size")
def api_size():
    body = request.get_json() or {}
    try:
        result = ex.position_size(
            account_size=float(body.get("account", 10_000)),
            entry_price=float(body["entry"]),
            stop_loss_price=float(body["stop"]),
            risk_pct=float(body.get("risk_pct", 1.0)),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.get("/api/auth/me")
def api_me():
    if current_user.is_authenticated:
        return jsonify(current_user.to_dict())
    return jsonify({"error": "Not authenticated"}), 401


@app.post("/api/auth/register")
def api_register():
    body = request.get_json() or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    name = (body.get("name") or "").strip()
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email is already registered"}), 400
    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    login_user(user, remember=True)
    return jsonify({"success": True, "user": user.to_dict()})


@app.post("/api/auth/login")
def api_login():
    body = request.get_json() or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401
    if not user.is_active:
        return jsonify({"error": "Account has been disabled — contact admin"}), 403
    login_user(user, remember=True)
    return jsonify({"success": True, "user": user.to_dict()})


@app.post("/api/auth/logout")
def api_logout():
    logout_user()
    return jsonify({"success": True})


# ── Wallet ────────────────────────────────────────────────────────────────────

@app.get("/api/wallet")
@login_required
def api_wallet():
    txs = (WalletTransaction.query
           .filter_by(user_id=current_user.id)
           .order_by(WalletTransaction.created_at.desc())
           .limit(30).all())
    return jsonify({
        "balance": round(current_user.wallet_balance, 2),
        "transactions": [t.to_dict() for t in txs],
    })


@app.post("/api/wallet/deposit")
@login_required
def api_wallet_deposit():
    from trading import payments as pay
    body = request.get_json() or {}
    try:
        amount = float(body.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400
    if amount < 10:
        return jsonify({"error": "Minimum deposit is $10"}), 400
    if amount > 50_000:
        return jsonify({"error": "Maximum single deposit is $50,000"}), 400
    if not pay.is_configured():
        return jsonify({"error": "STRIPE_SECRET_KEY is not configured"}), 400
    try:
        base = request.host_url.rstrip("/")
        url = pay.create_checkout_session(current_user.id, amount, base)
        # Record pending transaction
        tx = WalletTransaction(
            user_id=current_user.id, type="deposit", amount=amount,
            status="pending", note=f"Stripe checkout ${amount:.2f}",
        )
        db.session.add(tx)
        db.session.commit()
        return jsonify({"success": True, "checkout_url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/payment/webhook")
def api_payment_webhook():
    from trading import payments as pay
    event = pay.parse_webhook(request.get_data(), request.headers.get("Stripe-Signature", ""))
    if event is None:
        return jsonify({"error": "Invalid signature"}), 400
    if event.get("type") == "checkout.session.completed":
        sess = event["data"]["object"]
        user_id = int(sess.get("client_reference_id") or 0)
        amount = sess.get("amount_total", 0) / 100
        sid = sess.get("id", "")
        # Idempotency check
        if WalletTransaction.query.filter_by(stripe_session_id=sid, status="completed").first():
            return jsonify({"status": "already_processed"})
        user = User.query.get(user_id)
        if user:
            user.wallet_balance += amount
            tx = (WalletTransaction.query.filter_by(stripe_session_id=sid).first()
                  or WalletTransaction(user_id=user_id, type="deposit", amount=amount))
            tx.status = "completed"
            tx.stripe_session_id = sid
            tx.note = f"Stripe payment ${amount:.2f} confirmed"
            db.session.add(tx)
            db.session.commit()
    return jsonify({"status": "ok"})


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.get("/admin")
def admin_page():
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect("/?admin_login=1")
    return send_from_directory(app.static_folder, "admin.html")


@app.get("/api/admin/stats")
@_admin_required
def api_admin_stats():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_deposited = (
        db.session.query(db.func.sum(WalletTransaction.amount))
        .filter_by(type="deposit", status="completed").scalar() or 0
    )
    recent_txs = (WalletTransaction.query
                  .order_by(WalletTransaction.created_at.desc()).limit(25).all())
    return jsonify({
        "total_users": total_users,
        "active_users": active_users,
        "total_deposited": round(float(total_deposited), 2),
        "recent_transactions": [t.to_dict() for t in recent_txs],
    })


@app.get("/api/admin/users")
@_admin_required
def api_admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        total_dep = (
            db.session.query(db.func.sum(WalletTransaction.amount))
            .filter_by(user_id=u.id, type="deposit", status="completed").scalar() or 0
        )
        d = u.to_dict()
        d["total_deposited"] = round(float(total_dep), 2)
        result.append(d)
    return jsonify(result)


@app.get("/api/admin/users/<int:uid>/transactions")
@_admin_required
def api_admin_user_txs(uid):
    txs = (WalletTransaction.query.filter_by(user_id=uid)
           .order_by(WalletTransaction.created_at.desc()).limit(50).all())
    return jsonify([t.to_dict() for t in txs])


@app.post("/api/admin/users/<int:uid>/toggle")
@_admin_required
def api_admin_toggle(uid):
    user = User.query.get_or_404(uid)
    if user.is_admin:
        return jsonify({"error": "Cannot disable an admin account"}), 400
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({"success": True, "is_active": user.is_active})


@app.post("/api/admin/users/<int:uid>/adjust")
@_admin_required
def api_admin_adjust(uid):
    user = User.query.get_or_404(uid)
    body = request.get_json() or {}
    try:
        amount = float(body.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400
    note = (body.get("note") or "Admin adjustment").strip()
    user.wallet_balance = max(0.0, user.wallet_balance + amount)
    tx = WalletTransaction(user_id=uid, type="adjustment", amount=amount,
                           status="completed", note=note)
    db.session.add(tx)
    db.session.commit()
    return jsonify({"success": True, "new_balance": round(user.wallet_balance, 2)})


# ── Research & Barometer ─────────────────────────────────────────────────────

@app.get("/api/research/<symbol>")
def api_research(symbol):
    import io, contextlib, logging
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    info: dict = {}
    news: list = []
    try:
        import yfinance as yf
        buf = io.StringIO()
        t = yf.Ticker(symbol.upper())
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                info = t.info or {}
            except Exception:
                info = {}
            try:
                news = t.news or []
            except Exception:
                news = []
    except Exception:
        pass
    return jsonify({
            "symbol": symbol.upper(),
            "name": info.get("longName") or info.get("shortName", symbol.upper()),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "description": (info.get("longBusinessSummary") or "")[:600],
            "market_cap": _safe_float(info.get("marketCap")),
            "pe_ratio": _safe_float(info.get("trailingPE")),
            "forward_pe": _safe_float(info.get("forwardPE")),
            "eps": _safe_float(info.get("trailingEps")),
            "dividend_yield": _safe_float(info.get("dividendYield")),
            "beta": _safe_float(info.get("beta")),
            "week52_high": _safe_float(info.get("fiftyTwoWeekHigh")),
            "week52_low": _safe_float(info.get("fiftyTwoWeekLow")),
            "avg_volume": info.get("averageVolume"),
            "analyst_target": _safe_float(info.get("targetMeanPrice")),
            "recommendation": info.get("recommendationKey", ""),
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "website": info.get("website", ""),
            "news": [
                {"title": n.get("title", ""), "url": n.get("link", ""),
                 "publisher": n.get("publisher", ""), "time": n.get("providerPublishTime", 0)}
                for n in (news or [])[:8]
            ],
        })


@app.get("/api/barometer/<symbol>")
def api_barometer(symbol):
    try:
        df = mkt.fetch_ohlcv(symbol, period="6mo")
        df = ind.add_all_indicators(df)
        df2 = df.dropna(subset=["RSI_14"])
        if df2.empty:
            return jsonify({"error": "Insufficient data"}), 400
        row = df2.iloc[-1]
        prev = df2.iloc[-2] if len(df2) > 1 else row

        signals = []
        vs = []

        def sig(name, label, v):
            color = "buy" if v > 0.1 else "sell" if v < -0.1 else "neutral"
            signals.append({"indicator": name, "signal": label, "color": color})
            vs.append(v)

        rsi = row.get("RSI_14")
        if rsi is not None:
            if rsi < 30:    sig("RSI 14", "Oversold — Strong Buy", 1.0)
            elif rsi < 45:  sig("RSI 14", "Approaching Oversold — Buy", 0.5)
            elif rsi < 55:  sig("RSI 14", "Neutral", 0.0)
            elif rsi < 70:  sig("RSI 14", "Approaching Overbought — Sell", -0.5)
            else:           sig("RSI 14", "Overbought — Strong Sell", -1.0)

        m, ms = row.get("MACD"), row.get("MACD_Signal")
        if m is not None and ms is not None:
            mh = row.get("MACD_Hist") or 0
            mh_p = prev.get("MACD_Hist") or 0
            if m > ms and mh > mh_p:    sig("MACD", "Bullish & Accelerating", 1.0)
            elif m > ms:                 sig("MACD", "Bullish Crossover — Buy", 0.5)
            elif m < ms and mh < mh_p:   sig("MACD", "Bearish & Accelerating", -1.0)
            else:                        sig("MACD", "Bearish Crossover — Sell", -0.5)

        close, sma20, sma50 = row.get("Close"), row.get("SMA_20"), row.get("SMA_50")
        if all(v is not None for v in [close, sma20, sma50]):
            if close > sma20 > sma50:    sig("Moving Avg", "Golden Zone — Strong Buy", 1.0)
            elif close > sma20:           sig("Moving Avg", "Above SMA20 — Bullish", 0.5)
            elif close < sma20 < sma50:   sig("Moving Avg", "Death Zone — Strong Sell", -1.0)
            else:                         sig("Moving Avg", "Below SMA20 — Bearish", -0.5)

        bb = row.get("BB_PctB")
        if bb is not None:
            if bb < 0.15:    sig("Bollinger", "Near Lower Band — Strong Buy", 1.0)
            elif bb < 0.4:   sig("Bollinger", "Lower Half — Buy", 0.5)
            elif bb < 0.6:   sig("Bollinger", "Mid-Band — Neutral", 0.0)
            elif bb < 0.85:  sig("Bollinger", "Upper Half — Sell", -0.5)
            else:            sig("Bollinger", "Near Upper Band — Strong Sell", -1.0)

        ema12 = row.get("EMA_12")
        if ema12 is not None and close is not None:
            sig("EMA 12", "Price above EMA12 — Bullish" if close > ema12 else "Price below EMA12 — Bearish",
                0.5 if close > ema12 else -0.5)

        score = round((sum(vs) / len(vs) * 100) if vs else 0, 1)
        if score >= 60:    verdict = "Strong Buy"
        elif score >= 20:  verdict = "Buy"
        elif score >= -20: verdict = "Neutral"
        elif score >= -60: verdict = "Sell"
        else:              verdict = "Strong Sell"

        return jsonify({"symbol": symbol.upper(), "score": score, "verdict": verdict, "signals": signals})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ── Broker (Alpaca Markets) ───────────────────────────────────────────────────

@app.get("/api/broker/status")
def api_broker_status():
    try:
        from trading import broker as bkr
        return jsonify({
            "configured": bkr.is_configured(),
            "paper": os.environ.get("ALPACA_PAPER", "true").lower() != "false",
            "available": True,
        })
    except Exception:
        return jsonify({"configured": False, "paper": True, "available": False})


@app.get("/api/broker/account")
def api_broker_account():
    try:
        from trading import broker as bkr
        return jsonify(bkr.get_account())
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/broker/buy")
def api_broker_buy():
    try:
        from trading import broker as bkr
        body = request.get_json() or {}
        order = bkr.place_order(
            body.get("symbol", ""), "buy",
            qty=float(body["qty"]) if "qty" in body else None,
            notional=float(body["notional"]) if "notional" in body else None,
        )
        return jsonify({"success": True, "order": order})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/broker/sell")
def api_broker_sell():
    try:
        from trading import broker as bkr
        body = request.get_json() or {}
        order = bkr.place_order(
            body.get("symbol", ""), "sell",
            qty=float(body["qty"]) if "qty" in body else None,
        )
        return jsonify({"success": True, "order": order})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/broker/positions")
def api_broker_positions():
    try:
        from trading import broker as bkr
        return jsonify(bkr.get_positions())
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ── Education ─────────────────────────────────────────────────────────────────

@app.get("/api/learn/lessons")
def api_lessons():
    return jsonify([{"id": l["id"], "title": l["title"]} for l in edu.LESSONS])


@app.get("/api/learn/lesson/<int:lesson_id>")
def api_lesson(lesson_id):
    lesson = next((l for l in edu.LESSONS if l["id"] == lesson_id), None)
    if not lesson:
        return jsonify({"error": "Not found"}), 404
    return jsonify(lesson)


@app.get("/api/learn/glossary")
def api_glossary():
    return jsonify([{"term": k, "definition": v} for k, v in sorted(edu.GLOSSARY.items())])


# ── Entry ─────────────────────────────────────────────────────────────────────

def run(host="0.0.0.0", port=8080, debug=False):
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    run(port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
