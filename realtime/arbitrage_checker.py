"""
Simple arbitrage checker between Kalshi and Polymarket.
Checks if buying YES on one platform + NO on the other costs < $1.
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import time
from orderbook.Polymarket import polymarket_orderbook as poly
from orderbook.Kalshi import kalshi_orderbook as kalshi

# Configuration - Game with two teams
# Replace asset IDs with current events you want to observe/compare

# Kalshi
KALSHI_TICKER_TEAM1 = "KXATPMATCH-25NOV13ALCMUS-MUS"  # Team 1 (both YES/NO incorporated in toked id)
KALSHI_TICKER_TEAM2 = "KXATPMATCH-25NOV13ALCMUS-ALC"  # Team 2 (both YES/NO incorporated in token id)

#Polymarket
POLYMARKET_TOKEN_TEAM1_YES = "109655595673465428127666548452578838950869771961951026203723659164608814828397"  # Team 1 YES
POLYMARKET_TOKEN_TEAM1_NO = "86766168983643909333450861052975891736916487440642104341701077325121587506421"  # Team 1 NO (equivalent to Team 2 YES on Polymarket)


def check_arbitrage():
    """
    Check for arbitrage opportunities.

    Four strategies:
    1. Buy Polymarket Team1 YES + Buy Kalshi Team1 NO (same team, opposite outcomes)
    2. Buy Polymarket Team1 NO + Buy Kalshi Team1 YES (same team, opposite outcomes)
    3. Buy Polymarket Team1 YES + Buy Kalshi Team2 YES (both teams win - impossible, so profit if cost < $1)
    4. Buy Polymarket Team1 NO + Buy Kalshi Team2 NO (both teams lose - impossible, so profit if cost < $1)

    Strategies 1-2 cover all outcomes for same team.
    Strategies 3-4 bet on mutually exclusive outcomes (both can't happen).
    """
    # Get best ask prices for Team 1
    kalshi_team1_yes_ask = kalshi.get_best_yes_ask(KALSHI_TICKER_TEAM1)
    kalshi_team1_no_ask = kalshi.get_best_no_ask(KALSHI_TICKER_TEAM1)
    poly_team1_yes_ask = poly.get_best_ask(POLYMARKET_TOKEN_TEAM1_YES)
    poly_team1_no_ask = poly.get_best_ask(POLYMARKET_TOKEN_TEAM1_NO)

    # Get best ask prices for Team 2
    kalshi_team2_yes_ask = kalshi.get_best_yes_ask(KALSHI_TICKER_TEAM2)
    kalshi_team2_no_ask = kalshi.get_best_no_ask(KALSHI_TICKER_TEAM2)

    # Get best ask sizes for Team 1
    kalshi_team1_yes_ask_size = kalshi.get_best_yes_ask_size(KALSHI_TICKER_TEAM1)
    kalshi_team1_no_ask_size = kalshi.get_best_no_ask_size(KALSHI_TICKER_TEAM1)
    poly_team1_yes_ask_size = poly.get_best_ask_size(POLYMARKET_TOKEN_TEAM1_YES)
    poly_team1_no_ask_size = poly.get_best_ask_size(POLYMARKET_TOKEN_TEAM1_NO)

    # Get best ask sizes for Team 2
    kalshi_team2_yes_ask_size = kalshi.get_best_yes_ask_size(KALSHI_TICKER_TEAM2)
    kalshi_team2_no_ask_size = kalshi.get_best_no_ask_size(KALSHI_TICKER_TEAM2)

    # Check if we have all required data
    if not all([kalshi_team1_yes_ask, kalshi_team1_no_ask, poly_team1_yes_ask, poly_team1_no_ask,
                kalshi_team2_yes_ask, kalshi_team2_no_ask,
                kalshi_team1_yes_ask_size, kalshi_team1_no_ask_size, poly_team1_yes_ask_size, poly_team1_no_ask_size,
                kalshi_team2_yes_ask_size, kalshi_team2_no_ask_size]):
        return  # Not enough data yet

    # Strategy 1: Polymarket Team1 YES + Kalshi Team1 NO
    cost1 = poly_team1_yes_ask + kalshi_team1_no_ask
    profit1 = 1.0 - cost1
    tradable_size1 = min(poly_team1_yes_ask_size, kalshi_team1_no_ask_size)

    # Strategy 2: Polymarket Team1 NO + Kalshi Team1 YES
    cost2 = poly_team1_no_ask + kalshi_team1_yes_ask
    profit2 = 1.0 - cost2
    tradable_size2 = min(poly_team1_no_ask_size, kalshi_team1_yes_ask_size)

    # Strategy 3: Polymarket Team1 YES + Kalshi Team2 YES (both teams win)
    cost3 = poly_team1_yes_ask + kalshi_team2_yes_ask
    profit3 = 1.0 - cost3
    tradable_size3 = min(poly_team1_yes_ask_size, kalshi_team2_yes_ask_size)

    # Strategy 4: Polymarket Team1 NO + Kalshi Team2 NO (both teams lose)
    cost4 = poly_team1_no_ask + kalshi_team2_no_ask
    profit4 = 1.0 - cost4
    tradable_size4 = min(poly_team1_no_ask_size, kalshi_team2_no_ask_size)

    # Display results
    print(f"\n{'='*80}")
    print(f"ARBITRAGE CHECK - {time.strftime('%H:%M:%S')}")
    print(f"{'='*80}")
    print(f"Market Prices:")
    print(f"  Polymarket Team1 YES ask: ${poly_team1_yes_ask:.4f}")
    print(f"  Polymarket Team1 NO ask:  ${poly_team1_no_ask:.4f}")
    print(f"  Kalshi Team1 YES ask:     ${kalshi_team1_yes_ask:.4f}")
    print(f"  Kalshi Team1 NO ask:      ${kalshi_team1_no_ask:.4f}")
    print(f"  Kalshi Team2 YES ask:     ${kalshi_team2_yes_ask:.4f}")
    print(f"  Kalshi Team2 NO ask:      ${kalshi_team2_no_ask:.4f}")
    print()

    # Show all strategies
    strategies = [
        ("Strategy 1: Polymarket T1-YES + Kalshi T1-NO", cost1, profit1, tradable_size1),
        ("Strategy 2: Polymarket T1-NO + Kalshi T1-YES", cost2, profit2, tradable_size2),
        ("Strategy 3: Polymarket T1-YES + Kalshi T2-YES (cross-team)", cost3, profit3, tradable_size3),
        ("Strategy 4: Polymarket T1-NO + Kalshi T2-NO (cross-team)", cost4, profit4, tradable_size4),
    ]

    for strategy_name, cost, profit, tradable_size in strategies:
        print(f"{strategy_name}")
        print(f"  Total cost: ${cost:.4f} | Profit: ${profit:.4f} | Tradable: {tradable_size:.2f} contracts", end="")
        if profit > 0:
            print(f" ⚠️  ARBITRAGE!")
        elif profit == 0:
            print(f" (break-even)")
        else:
            print(f" (loss)")

    print(f"{'='*80}")


def main():
    """Run arbitrage checker."""
    print("="*80)
    print("ARBITRAGE CHECKER - Kalshi vs Polymarket (Cross-Platform)")
    print("="*80)
    print(f"Kalshi Team1: {KALSHI_TICKER_TEAM1}")
    print(f"Kalshi Team2: {KALSHI_TICKER_TEAM2}")
    print(f"Polymarket Team1 YES: {POLYMARKET_TOKEN_TEAM1_YES}")
    print(f"Polymarket Team1 NO:  {POLYMARKET_TOKEN_TEAM1_NO}")
    print("="*80)
    print("\nConnecting...")

    # Build list of tokens and tickers to monitor
    poly_tokens = [POLYMARKET_TOKEN_TEAM1_YES, POLYMARKET_TOKEN_TEAM1_NO]
    kalshi_tickers = [KALSHI_TICKER_TEAM1, KALSHI_TICKER_TEAM2]

    # Track last check time for debouncing (avoid checking too frequently)
    last_check_time = [0]  # Using list to allow mutation in callback
    MIN_CHECK_INTERVAL = 0.05  # Minimum 50ms between checks

    def on_orderbook_update(ticker_or_asset):
        """Callback triggered when any orderbook updates."""
        current_time = time.time()
        if current_time - last_check_time[0] >= MIN_CHECK_INTERVAL:
            last_check_time[0] = current_time
            check_arbitrage()

    # Register callbacks with both modules
    poly.register_update_callback(on_orderbook_update)
    kalshi.register_update_callback(on_orderbook_update)

    # Start both listeners in background threads
    poly.start_listener(poly_tokens)
    kalshi.start_listener(kalshi_tickers)

    # Wait for initial data
    print("\nWaiting for orderbook data...")
    time.sleep(3)

    print("\nMonitoring for arbitrage opportunities...")
    print("(Checks occur immediately on any orderbook update)")
    print()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopped.")


if __name__ == "__main__":
    main()
