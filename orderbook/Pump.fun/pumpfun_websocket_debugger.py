"""
Simple WebSocket client for pump.fun.
Connects, subscribes, and displays all messages.

Subscription types available:
- subscribeNewToken: Monitor new token creation
- subscribeTokenTrade: Track trades on specific token(s)
- subscribeAccountTrade: Monitor trades by specific account(s)
- subscribeMigration: Track token migration events

Note: pump.fun requires using a SINGLE WebSocket connection for all subscriptions.
Opening multiple connections may result in blacklisting.
"""
import json
import websocket

# Configuration
WS_URL = "wss://pumpportal.fun/api/data"

# Choose what to subscribe to
SUBSCRIPTION_TYPE = "subscribeTokenTrade"  # Options: subscribeNewToken, subscribeTokenTrade, subscribeAccountTrade, subscribeMigration

# For subscribeTokenTrade or subscribeAccountTrade, provide specific keys:
# Example token addresses or account addresses
KEYS = ["8QYwTt4tDdU9vFmww6r2svG9WCDQtpp7RMFYTZUDpump"]  # Add token/account addresses here if using subscribeTokenTrade or subscribeAccountTrade


def on_message(ws, message):
    """Print whatever the server sends."""
    print("\n" + "="*80)

    # Try to pretty-print if it's JSON, otherwise just print raw
    try:
        data = json.loads(message)
        print(json.dumps(data, indent=2))
    except:
        # Not JSON, print as-is
        print(message)

    print("="*80)


def on_error(ws, error):
    """Print errors."""
    print(f"\nERROR: {error}")


def on_close(ws, close_status_code, close_msg):
    """Print close info."""
    print(f"\nConnection closed: {close_status_code} - {close_msg}")


def on_open(ws):
    """Subscribe when connection opens."""
    print(f"Connected to {WS_URL}")

    # Build subscription message
    if SUBSCRIPTION_TYPE in ["subscribeNewToken", "subscribeMigration"]:
        # These don't require keys
        subscription = {
            "method": SUBSCRIPTION_TYPE
        }
    elif SUBSCRIPTION_TYPE in ["subscribeTokenTrade", "subscribeAccountTrade"]:
        # These require keys array
        if not KEYS:
            print(f"\nWARNING: {SUBSCRIPTION_TYPE} requires KEYS to be set!")
            print("Edit the script and add token/account addresses to KEYS list.\n")
            ws.close()
            return
        subscription = {
            "method": SUBSCRIPTION_TYPE,
            "keys": KEYS
        }
    else:
        print(f"\nERROR: Unknown subscription type: {SUBSCRIPTION_TYPE}")
        ws.close()
        return

    ws.send(json.dumps(subscription))
    print(f"Subscribed with method: {SUBSCRIPTION_TYPE}")
    if KEYS:
        print(f"Watching {len(KEYS)} key(s):")
        for i, key in enumerate(KEYS, 1):
            print(f"  {i}. {key[:20]}...")

    print("\nDisplaying ALL messages...")
    print("Press Ctrl+C to stop\n")


if __name__ == "__main__":
    print("="*80)
    print("PUMP.FUN WEBSOCKET DEBUGGER")
    print("="*80)
    print(f"Subscription: {SUBSCRIPTION_TYPE}")
    if KEYS:
        print(f"Keys: {len(KEYS)}")
    print("="*80 + "\n")

    # Create and run WebSocket
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    try:
        ws.run_forever()
    except KeyboardInterrupt:
        print("\n\nStopping...")
        ws.close()
