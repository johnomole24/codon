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

from flask import Flask, jsonify, request, send_from_directory
import pandas as pd
import numpy as np

from trading import data as mkt
from trading import indicators as ind
from trading import strategies as strat
from trading import learn as edu
from trading.portfolio import Portfolio
from trading import executor as ex

app = Flask(__name__, static_folder="static", static_url_path="")

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
        portfolio = Portfolio()
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
        portfolio = Portfolio()
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
        portfolio = Portfolio()
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
        Portfolio().reset(capital)
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
