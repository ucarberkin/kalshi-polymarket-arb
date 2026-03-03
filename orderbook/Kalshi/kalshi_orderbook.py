"""
Kalshi orderbook WebSocket client - COPIED FROM WORKING kalshi_realtime_orderbook.py
"""
import time
import base64
import asyncio
import json
import threading
import websockets
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from collections import defaultdict
from config_paths import read_secret_text, read_secret_bytes

# Kalshi API
WS_HOST = "wss://api.elections.kalshi.com"
WS_PATH = "/trade-api/ws/v2"

# Load credentials
KEY_ID = read_secret_text("kalshi_api.txt", env_var="KALSHI_API_FILE")
raw = read_secret_bytes("kalshi_private_key.pem", env_var="KALSHI_PRIVATE_KEY_FILE")
if b"\\n" in raw and b"\n" not in raw:
    raw = raw.replace(b"\\n", b"\n")
priv = serialization.load_pem_private_key(raw, password=None)

# Orderbook storage: {market_ticker: {"yes": {price: size, ...}, "no": {price: size, ...}}}
orderbooks = defaultdict(lambda: {"yes": {}, "no": {}})

# Callbacks to notify on orderbook updates: list of functions(ticker)
update_callbacks = []


def ws_headers():
    """Generate authentication headers for WebSocket connection."""
    ts = str(int(time.time() * 1000))
    to_sign = f"{ts}GET{WS_PATH}".encode()
    sig = priv.sign(
        to_sign,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }


def process_orderbook_snapshot(data):
    """Process full orderbook snapshot - replace entire orderbook."""
    msg = data.get("msg", {})
    ticker = msg.get("market_ticker")

    if not ticker:
        return

    print(f"[Kalshi DEBUG] Snapshot for {ticker}: {len(msg.get('yes', []))} YES, {len(msg.get('no', []))} NO")

    # Clear and rebuild orderbook
    orderbooks[ticker]["yes"] = {}
    orderbooks[ticker]["no"] = {}

    # Process yes side (each entry is [price, size])
    for price, size in msg.get("yes", []):
        if size > 0:
            orderbooks[ticker]["yes"][price] = size

    # Process no side
    for price, size in msg.get("no", []):
        if size > 0:
            orderbooks[ticker]["no"][price] = size

    # Notify callbacks
    for callback in update_callbacks:
        try:
            callback(ticker)
        except Exception as e:
            print(f"[Kalshi] Callback error: {e}")


def process_orderbook_delta(data):
    """Process orderbook delta - update specific price levels.

    Delta format: Each message updates ONE price level:
    {
        "market_ticker": "...",
        "price": 68,           # Price in cents
        "delta": -169,         # Size change (positive = add, negative = remove)
        "side": "yes" or "no"
    }
    """
    msg = data.get("msg", {})
    ticker = msg.get("market_ticker")

    if not ticker:
        return

    price = msg.get("price")
    delta = msg.get("delta")
    side = msg.get("side")

    if price is None or delta is None or side not in ["yes", "no"]:
        return

    # Get current size at this price level
    current_size = orderbooks[ticker][side].get(price, 0)
    new_size = current_size + delta

    if new_size <= 0:
        # Remove the price level
        orderbooks[ticker][side].pop(price, None)
    else:
        # Update the price level
        orderbooks[ticker][side][price] = new_size

    # Notify callbacks
    for callback in update_callbacks:
        try:
            callback(ticker)
        except Exception as e:
            print(f"[Kalshi] Callback error: {e}")


async def connect(tickers):
    """Connect to Kalshi WebSocket and maintain real-time orderbook."""
    try:
        async with websockets.connect(WS_HOST + WS_PATH, additional_headers=ws_headers()) as ws:
            print("[Kalshi] Connected")

            # Subscribe to orderbook deltas for each ticker
            for ticker in tickers:
                subscription = {
                    "id": 1,
                    "cmd": "subscribe",
                    "params": {
                        "channels": ["orderbook_delta"],
                        "market_ticker": ticker
                    }
                }
                await ws.send(json.dumps(subscription))

            print(f"[Kalshi] Subscribed to {len(tickers)} ticker(s)")

            # Process messages
            msg_count = 0
            while True:
                msg = await ws.recv()
                msg_count += 1
                data = json.loads(msg)
                msg_type = data.get("type")

                # Optionally log message count (commented out for production)
                # print(f"[Kalshi] Message #{msg_count}: type={msg_type}")

                if msg_type == "orderbook_snapshot":
                    process_orderbook_snapshot(data)
                elif msg_type == "orderbook_delta":
                    process_orderbook_delta(data)
                # Ignore other message types (subscribed, error, etc.)

    except Exception as e:
        print(f"[Kalshi] ERROR in connect: {e}")
        import traceback
        traceback.print_exc()


def run_event_loop(tickers):
    """Run asyncio event loop in thread."""
    try:
        asyncio.run(connect(tickers))
    except Exception as e:
        print(f"[Kalshi] ERROR in run_event_loop: {e}")
        import traceback
        traceback.print_exc()


def start_listener(tickers, daemon=True):
    """
    Start Kalshi WebSocket listener in a background thread.

    Args:
        tickers: List of market tickers to subscribe to
        daemon: Whether to run as daemon thread (default True)

    Returns:
        Thread object
    """
    thread = threading.Thread(target=run_event_loop, args=(tickers,), daemon=daemon)
    thread.start()
    return thread


def get_orderbook(ticker):
    """
    Get the current orderbook for a ticker.

    Args:
        ticker: The market ticker

    Returns:
        Dict with "yes" and "no" sides (BID prices), or None if not available
    """
    if ticker not in orderbooks:
        return None
    return {"yes": dict(orderbooks[ticker]["yes"]), "no": dict(orderbooks[ticker]["no"])}


def get_best_yes_ask(ticker):
    """
    Get the best (lowest) YES ask price.

    In Kalshi: YES ASK = 100 - (best NO BID)
    """
    if ticker not in orderbooks or not orderbooks[ticker]["no"]:
        return None
    best_no_bid = max(orderbooks[ticker]["no"].keys())
    return (100 - best_no_bid) / 100.0


def get_best_no_ask(ticker):
    """
    Get the best (lowest) NO ask price.

    In Kalshi: NO ASK = 100 - (best YES BID)
    """
    if ticker not in orderbooks or not orderbooks[ticker]["yes"]:
        return None
    best_yes_bid = max(orderbooks[ticker]["yes"].keys())
    return (100 - best_yes_bid) / 100.0


def get_best_yes_bid(ticker):
    """
    Get the best (highest) YES bid price.
    """
    if ticker not in orderbooks or not orderbooks[ticker]["yes"]:
        return None
    return max(orderbooks[ticker]["yes"].keys()) / 100.0


def get_best_no_bid(ticker):
    """
    Get the best (highest) NO bid price.
    """
    if ticker not in orderbooks or not orderbooks[ticker]["no"]:
        return None
    return max(orderbooks[ticker]["no"].keys()) / 100.0


def get_best_yes_ask_size(ticker):
    """
    Get the size available at the best YES ask price.

    In Kalshi: YES ASK = 100 - (best NO BID)
    So we return the size at the best NO bid price.
    """
    if ticker not in orderbooks or not orderbooks[ticker]["no"]:
        return None
    best_no_bid_price = max(orderbooks[ticker]["no"].keys())
    return orderbooks[ticker]["no"][best_no_bid_price]


def get_best_no_ask_size(ticker):
    """
    Get the size available at the best NO ask price.

    In Kalshi: NO ASK = 100 - (best YES BID)
    So we return the size at the best YES bid price.
    """
    if ticker not in orderbooks or not orderbooks[ticker]["yes"]:
        return None
    best_yes_bid_price = max(orderbooks[ticker]["yes"].keys())
    return orderbooks[ticker]["yes"][best_yes_bid_price]


def get_best_yes_bid_size(ticker):
    """
    Get the size available at the best YES bid price.
    """
    if ticker not in orderbooks or not orderbooks[ticker]["yes"]:
        return None
    best_yes_bid_price = max(orderbooks[ticker]["yes"].keys())
    return orderbooks[ticker]["yes"][best_yes_bid_price]


def get_best_no_bid_size(ticker):
    """
    Get the size available at the best NO bid price.
    """
    if ticker not in orderbooks or not orderbooks[ticker]["no"]:
        return None
    best_no_bid_price = max(orderbooks[ticker]["no"].keys())
    return orderbooks[ticker]["no"][best_no_bid_price]


def register_update_callback(callback):
    """
    Register a callback function to be called when orderbook updates.

    Args:
        callback: Function that takes (ticker) as parameter
    """
    update_callbacks.append(callback)
