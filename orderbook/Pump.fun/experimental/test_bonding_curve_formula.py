"""
Test pump.fun bonding curve formula against real trade data.

Formula from Binance Square post:
y = 1073000191 - 32190005730/(30+x)

Where:
- x = cumulative SOL purchased
- y = tokens obtained for that purchase
- Price per token = SOL_spent / tokens_received

This script:
1. Connects to pump.fun WebSocket
2. Collects real trades
3. Calculates predicted prices using the formula
4. Compares predicted vs actual
5. Reports accuracy statistics
"""
import json
import time
import websocket
from collections import defaultdict

# Configuration
TOKEN_ADDRESS = None  # Set to None to auto-find active token, or specify address
WS_URL = "wss://pumpportal.fun/api/data"
COLLECT_DURATION = 120  # seconds to collect data

# Bonding curve constants (from Binance post)
VIRTUAL_TOKEN_INITIAL = 1_073_000_191
K_CONSTANT = 32_190_005_730
VIRTUAL_SOL_INITIAL = 30

# Results storage
trades = []
k_values = []  # Track if k is constant
active_token = TOKEN_ADDRESS  # Will be set if TOKEN_ADDRESS is None


def calculate_expected_tokens_from_reserves(v_sol_before, v_tokens_before, sol_amount):
    """
    Calculate expected tokens using constant product formula.

    Formula: x * y = k (constant)
    Where:
    - x = vSolInBondingCurve
    - y = vTokensInBondingCurve
    - k should remain constant

    For a buy:
    - SOL increases: x_new = x_old + sol_amount
    - Tokens decrease: y_new = k / x_new
    - Tokens obtained = y_old - y_new
    """
    k = v_sol_before * v_tokens_before
    v_sol_after = v_sol_before + sol_amount
    v_tokens_after = k / v_sol_after
    tokens_obtained = v_tokens_before - v_tokens_after
    return tokens_obtained, k


def on_message(ws, message):
    """Process incoming trade messages."""
    global active_token

    try:
        data = json.loads(message)

        # If we don't have an active token yet, grab the first one we see
        if active_token is None:
            if "mint" in data:
                active_token = data["mint"]
                print(f"\nFound active token: {active_token}")
                print("Resubscribing to track this token's trades...")

                # Resubscribe to this specific token's trades
                subscription = {
                    "method": "subscribeTokenTrade",
                    "keys": [active_token]
                }
                ws.send(json.dumps(subscription))
                print("Now collecting trades...\n")
            return

        # Check for pump.fun trade message
        if "signature" in data and "txType" in data:
            # Extract trade details from actual message format
            sol_amount = data.get("solAmount")
            token_amount = data.get("tokenAmount")
            trade_type = data.get("txType")  # "buy" or "sell"
            v_sol_after = data.get("vSolInBondingCurve")  # Reserves AFTER trade
            v_tokens_after = data.get("vTokensInBondingCurve")  # Reserves AFTER trade
            market_cap = data.get("marketCapSol")
            signature = data.get("signature")

            # Only process buys for now (sells work inversely)
            if trade_type == "buy" and sol_amount and token_amount and v_sol_after and v_tokens_after:
                # Calculate reserves BEFORE trade
                v_sol_before = v_sol_after - sol_amount
                v_tokens_before = v_tokens_after + token_amount

                # Calculate what formula predicts
                predicted_tokens, k = calculate_expected_tokens_from_reserves(
                    v_sol_before, v_tokens_before, sol_amount
                )

                # Calculate k after trade (should be same)
                k_after = v_sol_after * v_tokens_after
                k_values.append(k)

                # Calculate errors
                error_pct = abs(predicted_tokens - token_amount) / token_amount * 100 if token_amount > 0 else 0
                k_drift_pct = abs(k - k_after) / k * 100 if k > 0 else 0

                # Store result
                trade_result = {
                    "signature": signature[:16] + "...",
                    "sol_amount": sol_amount,
                    "actual_tokens": token_amount,
                    "predicted_tokens": predicted_tokens,
                    "error_pct": error_pct,
                    "k_before": k,
                    "k_after": k_after,
                    "k_drift_pct": k_drift_pct,
                    "v_sol_before": v_sol_before,
                    "v_tokens_before": v_tokens_before,
                    "market_cap_sol": market_cap
                }
                trades.append(trade_result)

                print(f"\nTrade #{len(trades)}:")
                print(f"  Type: {trade_type}")
                print(f"  SOL: {sol_amount:.6f}")
                print(f"  Actual tokens: {token_amount:,.2f}")
                print(f"  Predicted tokens: {predicted_tokens:,.2f}")
                print(f"  Error: {error_pct:.3f}%")
                print(f"  k drift: {k_drift_pct:.6f}%")

    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"Error processing message: {e}")


def on_error(ws, error):
    print(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    print(f"\nWebSocket closed: {close_status_code} - {close_msg}")


def on_open(ws):
    print(f"Connected to {WS_URL}")

    if TOKEN_ADDRESS is None:
        print("Waiting for first active token to appear...")
        # Subscribe to new token creation to find an active token
        subscription = {
            "method": "subscribeNewToken"
        }
    else:
        print(f"Subscribing to token: {TOKEN_ADDRESS}")
        subscription = {
            "method": "subscribeTokenTrade",
            "keys": [TOKEN_ADDRESS]
        }

    ws.send(json.dumps(subscription))

    print(f"\nCollecting trades for {COLLECT_DURATION} seconds...")
    print("Press Ctrl+C to stop early\n")


def print_results():
    """Print statistical analysis of formula accuracy."""
    print("\n" + "="*80)
    print("FORMULA VALIDATION RESULTS")
    print("="*80)

    if not trades:
        print("No trades collected!")
        return

    print(f"\nTotal trades collected: {len(trades)}")

    # Calculate statistics
    errors = [t["error_pct"] for t in trades]
    avg_error = sum(errors) / len(errors)
    max_error = max(errors)
    min_error = min(errors)

    print(f"\nError Statistics:")
    print(f"  Average error: {avg_error:.2f}%")
    print(f"  Max error: {max_error:.2f}%")
    print(f"  Min error: {min_error:.2f}%")

    # Accuracy assessment
    print(f"\nAccuracy Assessment:")
    accurate_trades = sum(1 for e in errors if e < 1.0)  # < 1% error
    reasonable_trades = sum(1 for e in errors if e < 5.0)  # < 5% error

    print(f"  < 1% error: {accurate_trades}/{len(trades)} ({accurate_trades/len(trades)*100:.1f}%)")
    print(f"  < 5% error: {reasonable_trades}/{len(trades)} ({reasonable_trades/len(trades)*100:.1f}%)")

    # Show sample trades
    print(f"\nSample trades:")
    for i, trade in enumerate(trades[:5]):
        print(f"\n  Trade {i+1}:")
        print(f"    SOL: {trade['sol_amount']}")
        print(f"    Actual: {trade['actual_tokens']} tokens")
        print(f"    Predicted: {trade['predicted_tokens']:.2f} tokens")
        print(f"    Error: {trade['error_pct']:.2f}%")

    # Conclusion
    print(f"\n" + "="*80)
    if avg_error < 1.0:
        print("CONCLUSION: Formula appears HIGHLY ACCURATE ✓")
    elif avg_error < 5.0:
        print("CONCLUSION: Formula appears REASONABLY ACCURATE")
    elif avg_error < 10.0:
        print("CONCLUSION: Formula has MODERATE ACCURACY - may need adjustments")
    else:
        print("CONCLUSION: Formula appears INACCURATE - likely wrong formula or parameters")
    print("="*80)


if __name__ == "__main__":
    print("="*80)
    print("PUMP.FUN BONDING CURVE FORMULA VALIDATOR")
    print("="*80)
    print(f"\nFormula: y = {VIRTUAL_TOKEN_INITIAL} - {K_CONSTANT}/(30+x)")
    if TOKEN_ADDRESS:
        print(f"Token: {TOKEN_ADDRESS}")
    else:
        print("Token: Auto-detect (will track first active token found)")
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
        # Run for specified duration
        import threading
        ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
        ws_thread.start()

        # Wait for collection period
        time.sleep(COLLECT_DURATION)

        # Close connection
        ws.close()
        ws_thread.join(timeout=2)

    except KeyboardInterrupt:
        print("\n\nStopping early...")
        ws.close()

    # Print results
    print_results()
