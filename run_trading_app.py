#!/usr/bin/env python3
"""
Start the Codon Trading mobile PWA.

Usage:
  python run_trading_app.py [--port 8080] [--host 0.0.0.0]

Then open http://localhost:8080 in your browser (or on your phone
if both devices share the same network).

To install as a mobile app:
  iOS: Safari → Share → Add to Home Screen
  Android: Chrome menu → Add to Home Screen / Install App
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from trading.app.server import run

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Codon Trading PWA")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()

    print(f"""
╔══════════════════════════════════════════════╗
║         Codon Trading — Mobile PWA           ║
╠══════════════════════════════════════════════╣
║  Local:   http://localhost:{args.port}             ║
║  Network: http://<your-ip>:{args.port}             ║
╠══════════════════════════════════════════════╣
║  Install on mobile:                          ║
║  iOS     → Safari → Share → Add to Home      ║
║  Android → Chrome → ⋮ → Add to Home Screen  ║
╚══════════════════════════════════════════════╝
""")
    run(host=args.host, port=args.port, debug=args.debug)
