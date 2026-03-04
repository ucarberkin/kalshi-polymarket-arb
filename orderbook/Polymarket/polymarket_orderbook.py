"""
Polymarket orderbook WebSocket client
"""
import json
import threading
import websocket

# WebSocket URL
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Global orderbook state: asset_id -> {"bids": {price: size}, "asks": {price: size}}
orderbooks = {}

# Callbacks to notify on orderbook updates: list of functions(asset_id)
update_callbacks = []


def process_book_event(message):
    """Process 'book' event - full orderbook snapshot."""
    asset_id = message.get("asset_id")
    if not asset_id:
        return

    # Initialize orderbook for this asset
    if asset_id not in orderbooks:
        orderbooks[asset_id] = {"bids": {}, "asks": {}}

    # Replace entire orderbook
    orderbooks[asset_id]["bids"] = {}
    orderbooks[asset_id]["asks"] = {}

    # Populate bids
    for bid in message.get("bids", []):
        price = bid.get("price")
        size = bid.get("size")
        if price and size:
            orderbooks[asset_id]["bids"][price] = size

    # Populate asks
    for ask in message.get("asks", []):
        price = ask.get("price")
        size = ask.get("size")
        if price and size:
            orderbooks[asset_id]["asks"][price] = size

    # Notify callbacks
    for callback in update_callbacks:
        try:
            callback(asset_id)
        except Exception as e:
            print(f"[Polymarket] Callback error: {e}")


def process_price_change_event(message):
    """Process 'price_change' event - update specific price level."""
    price_changes = message.get("price_changes", [])

    for change in price_changes:
        asset_id = change.get("asset_id")
        if not asset_id:
            continue

        # Initialize orderbook if needed
        if asset_id not in orderbooks:
            orderbooks[asset_id] = {"bids": {}, "asks": {}}

        price = change.get("price")
        size = change.get("size")
        side = change.get("side")  # "BUY" or "SELL"

        if not price or not size or not side:
            continue

        # Update the specific price level
        if side == "BUY":
            if float(size) == 0:
                orderbooks[asset_id]["bids"].pop(price, None)
            else:
                orderbooks[asset_id]["bids"][price] = size
        elif side == "SELL":
            if float(size) == 0:
                orderbooks[asset_id]["asks"].pop(price, None)
            else:
                orderbooks[asset_id]["asks"][price] = size

        # Notify callbacks for this asset
        for callback in update_callbacks:
            try:
                callback(asset_id)
            except Exception as e:
                print(f"[Polymarket] Callback error: {e}")


def on_message(ws, message):
    """Handle incoming WebSocket messages."""
    if message.strip() in ["PONG", "PING"]:
        return

    try:
        data = json.loads(message)

        # Handle both single dict and array of messages
        messages = [data] if isinstance(data, dict) else data if isinstance(data, list) else []

        for msg in messages:
            if not isinstance(msg, dict):
                continue

            event_type = msg.get("event_type")

            if event_type == "book":
                process_book_event(msg)
            elif event_type == "price_change":
                process_price_change_event(msg)

    except Exception as e:
        print(f"[Polymarket] Error: {e}")


def on_error(ws, error):
    """Handle WebSocket errors."""
    print(f"[Polymarket] ERROR: {error}")


def on_close(ws, close_status_code, close_msg):
    """Handle WebSocket close."""
    print(f"[Polymarket] Connection closed: {close_status_code} - {close_msg}")


def on_open(ws):
    """Subscribe to assets when connection opens."""
    print(f"[Polymarket] Connected")

    # Get asset IDs from the ws object (stored during creation)
    asset_ids = getattr(ws, 'asset_ids', [])

    subscription = {
        "assets_ids": asset_ids,
        "type": "market"
    }

    ws.send(json.dumps(subscription))
    print(f"[Polymarket] Subscribed to {len(asset_ids)} asset(s)")


def start_listener(asset_ids, daemon=True):
    """
    Start Polymarket WebSocket listener in a background thread.

    Args:
        asset_ids: List of asset IDs to subscribe to
        daemon: Whether to run as daemon thread (default True)

    Returns:
        Thread object
    """
    def run_websocket():
        ws = websocket.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        # Store asset_ids in the ws object so on_open can access it
        ws.asset_ids = asset_ids
        ws.run_forever()

    thread = threading.Thread(target=run_websocket, daemon=daemon)
    thread.start()
    return thread


def get_orderbook(asset_id):
    """
    Get the current orderbook for an asset.

    Args:
        asset_id: The asset ID

    Returns:
        Dict with "bids" and "asks", or None if not available
    """
    return orderbooks.get(asset_id)


def get_best_ask(asset_id):
    """
    Get the best (lowest) ask price for an asset.

    Args:
        asset_id: The asset ID

    Returns:
        Float price or None if not available
    """
    book = orderbooks.get(asset_id)
    if not book or not book["asks"]:
        return None
    return min(float(p) for p in book["asks"].keys())


def get_best_bid(asset_id):
    """
    Get the best (highest) bid price for an asset.

    Args:
        asset_id: The asset ID

    Returns:
        Float price or None if not available
    """
    book = orderbooks.get(asset_id)
    if not book or not book["bids"]:
        return None
    return max(float(p) for p in book["bids"].keys())


def get_best_ask_size(asset_id):
    """
    Get the size available at the best (lowest) ask price for an asset.

    Args:
        asset_id: The asset ID

    Returns:
        Float size or None if not available
    """
    book = orderbooks.get(asset_id)
    if not book or not book["asks"]:
        return None
    best_ask_price = min(book["asks"].keys())
    return float(book["asks"][best_ask_price])


def get_best_bid_size(asset_id):
    """
    Get the size available at the best (highest) bid price for an asset.

    Args:
        asset_id: The asset ID

    Returns:
        Float size or None if not available
    """
    book = orderbooks.get(asset_id)
    if not book or not book["bids"]:
        return None
    best_bid_price = max(book["bids"].keys())
    return float(book["bids"][best_bid_price])


def register_update_callback(callback):
    """
    Register a callback function to be called when orderbook updates.

    Args:
        callback: Function that takes (asset_id) as parameter
    """
    update_callbacks.append(callback)
