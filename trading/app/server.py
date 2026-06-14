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
    run(debug=True)
