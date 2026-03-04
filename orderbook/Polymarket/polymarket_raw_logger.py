"""
High-performance raw WebSocket data logger for Polymarket.

Saves raw messages to JSON Lines format with minimal latency.
Features:
- Direct disk writes with buffering
- Async file I/O via threading
- Automatic file rotation (configurable duration)
- Zero message parsing (writes raw JSON)
- Minimal overhead for maximum speed
"""
import json
import websocket
import threading
import time
import argparse
from datetime import datetime
from pathlib import Path
from collections import deque

# Configuration
# Replace asset IDs with current events you want to observe
ASSET_IDS = [
    "109081243913383015615425037992636571273513271639233491652524900113026919029196",
    "32032245236655318400797290255881067171693430317457825461889587709601561202503"
]

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DATA_DIR = "./polymarket_raw_data"

# Performance settings
BUFFER_SIZE = 100  # Write to disk every N messages
FLUSH_INTERVAL = 1.0  # Or every N seconds (whichever comes first)


class RawDataLogger:
    """High-performance logger for raw WebSocket data."""

    def __init__(self, asset_ids, data_dir=DATA_DIR, rotation_interval=3600, auto_stop_after=None):
        self.asset_ids = asset_ids
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.rotation_interval = rotation_interval  # Seconds between file rotations
        self.auto_stop_after = auto_stop_after  # Seconds before auto-stop (None = run forever)

        # Message buffer (thread-safe)
        self.buffer = deque()
        self.buffer_lock = threading.Lock()

        # File handles
        self.current_file = None
        self.file_start_time = None

        # Stats
        self.messages_received = 0
        self.messages_written = 0
        self.bytes_written = 0
        self.start_time = None

        # Control
        self.running = False
        self.flush_thread = None
        self.auto_stop_thread = None
        self.ws = None  # WebSocket instance (set externally)

    def get_filename(self):
        """Generate filename based on current timestamp."""
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        return self.data_dir / f"polymarket_{timestamp_str}.jsonl"

    def rotate_file_if_needed(self):
        """Check if we need to rotate to a new file based on rotation interval."""
        now = time.time()

        # Rotate if file doesn't exist or rotation interval elapsed
        should_rotate = False

        if self.current_file is None:
            should_rotate = True
        elif self.file_start_time and (now - self.file_start_time) >= self.rotation_interval:
            should_rotate = True

        if should_rotate:
            # Close old file
            if self.current_file:
                self.current_file.close()
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Rotated to new file")

            # Open new file
            filename = self.get_filename()
            self.current_file = open(filename, 'a', buffering=8192)  # 8KB buffer
            self.file_start_time = now

            # Print rotation info
            if self.rotation_interval >= 3600:
                interval_str = f"{self.rotation_interval/3600:.1f} hours"
            elif self.rotation_interval >= 60:
                interval_str = f"{self.rotation_interval/60:.1f} minutes"
            else:
                interval_str = f"{self.rotation_interval} seconds"

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Writing to: {filename}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Next rotation in: {interval_str}")

    def add_message(self, message):
        """Add message to buffer (called from WebSocket thread)."""
        with self.buffer_lock:
            self.buffer.append(message)
            self.messages_received += 1

    def flush_buffer(self):
        """Write buffered messages to disk."""
        # Get messages from buffer
        with self.buffer_lock:
            if not self.buffer:
                return
            messages = list(self.buffer)
            self.buffer.clear()

        # Rotate file if needed
        self.rotate_file_if_needed()

        # Write messages
        for msg in messages:
            try:
                # Add timestamp and write as single line
                data = {
                    "received_at": datetime.now().isoformat(),
                    "message": json.loads(msg) if isinstance(msg, str) else msg
                }
                line = json.dumps(data) + '\n'
                self.current_file.write(line)
                self.bytes_written += len(line)
                self.messages_written += 1

            except Exception as e:
                print(f"Error writing message: {e}")

        # Ensure it's written to disk
        self.current_file.flush()

    def flush_loop(self):
        """Background thread to flush buffer periodically."""
        last_flush = time.time()

        while self.running:
            time.sleep(0.1)  # Check every 100ms

            now = time.time()
            should_flush = False

            with self.buffer_lock:
                buffer_size = len(self.buffer)

            # Flush if buffer is full or time elapsed
            if buffer_size >= BUFFER_SIZE:
                should_flush = True
            elif buffer_size > 0 and (now - last_flush) >= FLUSH_INTERVAL:
                should_flush = True

            if should_flush:
                self.flush_buffer()
                last_flush = now

    def auto_stop_loop(self):
        """Background thread to auto-stop after specified duration."""
        time.sleep(self.auto_stop_after)

        if self.running:
            print(f"\n{'='*80}")
            print(f"AUTO-STOP: {self.auto_stop_after} seconds elapsed")
            print(f"{'='*80}")
            self.stop()

            # Close WebSocket to exit cleanly
            if self.ws:
                self.ws.close()

    def start(self):
        """Start the logger."""
        self.running = True
        self.start_time = time.time()

        # Start flush thread
        self.flush_thread = threading.Thread(target=self.flush_loop, daemon=True)
        self.flush_thread.start()

        # Start auto-stop thread if configured
        if self.auto_stop_after:
            self.auto_stop_thread = threading.Thread(target=self.auto_stop_loop, daemon=True)
            self.auto_stop_thread.start()

        # Format rotation interval for display
        if self.rotation_interval >= 3600:
            rotation_str = f"{self.rotation_interval/3600:.1f} hours"
        elif self.rotation_interval >= 60:
            rotation_str = f"{self.rotation_interval/60:.1f} minutes"
        else:
            rotation_str = f"{self.rotation_interval} seconds"

        # Format auto-stop for display
        if self.auto_stop_after:
            if self.auto_stop_after >= 3600:
                auto_stop_str = f"{self.auto_stop_after/3600:.1f} hours"
            elif self.auto_stop_after >= 60:
                auto_stop_str = f"{self.auto_stop_after/60:.1f} minutes"
            else:
                auto_stop_str = f"{self.auto_stop_after} seconds"
        else:
            auto_stop_str = "disabled (run forever)"

        print(f"\n{'='*80}")
        print("RAW DATA LOGGER STARTED")
        print(f"{'='*80}")
        print(f"Data directory: {self.data_dir}")
        print(f"Buffer size: {BUFFER_SIZE} messages")
        print(f"Flush interval: {FLUSH_INTERVAL}s")
        print(f"File rotation: {rotation_str}")
        print(f"Auto-stop: {auto_stop_str}")
        print(f"{'='*80}\n")

    def stop(self):
        """Stop the logger and flush remaining data."""
        print("\nStopping logger...")
        self.running = False

        # Wait for flush thread
        if self.flush_thread:
            self.flush_thread.join()

        # Final flush
        self.flush_buffer()

        # Close file
        if self.current_file:
            self.current_file.close()

        print(f"\n{'='*80}")
        print("LOGGER STOPPED - STATISTICS")
        print(f"{'='*80}")
        print(f"Messages received: {self.messages_received:,}")
        print(f"Messages written: {self.messages_written:,}")
        print(f"Bytes written: {self.bytes_written:,}")
        print(f"{'='*80}\n")

    def print_stats(self):
        """Print current statistics."""
        with self.buffer_lock:
            buffer_size = len(self.buffer)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"Recv: {self.messages_received:,} | "
              f"Written: {self.messages_written:,} | "
              f"Buffer: {buffer_size} | "
              f"Bytes: {self.bytes_written:,}")


# Global logger instance
logger = None


def on_message(ws, message):
    """Handle incoming WebSocket messages - minimal processing."""
    # Skip control messages
    if message.strip() in ["PONG", "PING"]:
        return

    # Add to buffer (ultra-fast, just append to deque)
    logger.add_message(message)


def on_error(ws, error):
    """Print errors."""
    print(f"\nERROR: {error}")


def on_close(ws, close_status_code, close_msg):
    """Print close info."""
    print(f"\nConnection closed: {close_status_code} - {close_msg}")


def on_open(ws):
    """Subscribe to assets when connection opens."""
    print(f"Connected to {WS_URL}")

    subscription = {
        "assets_ids": ASSET_IDS,
        "type": "market"
    }

    ws.send(json.dumps(subscription))
    print(f"Subscribed to {len(ASSET_IDS)} assets\n")


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="High-performance raw WebSocket data logger for Polymarket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default (1 hour rotation, run forever)
  python polymarket_raw_logger.py

  # Rotate every 30 minutes
  python polymarket_raw_logger.py --rotation-interval 1800

  # Auto-stop after 2 hours
  python polymarket_raw_logger.py --auto-stop 7200

  # Rotate every 10 minutes AND auto-stop after 1 hour
  python polymarket_raw_logger.py --rotation-interval 600 --auto-stop 3600

  # Run for 30 seconds (quick test)
  python polymarket_raw_logger.py --auto-stop 30 --rotation-interval 10
        """
    )

    parser.add_argument(
        '--rotation-interval',
        type=int,
        default=3600,
        help='File rotation interval in seconds (default: 3600 = 1 hour)'
    )

    parser.add_argument(
        '--auto-stop',
        type=int,
        default=None,
        help='Auto-stop after N seconds (default: None = run forever)'
    )

    parser.add_argument(
        '--data-dir',
        type=str,
        default=DATA_DIR,
        help=f'Directory to save data files (default: {DATA_DIR})'
    )

    args = parser.parse_args()

    print("="*80)
    print("POLYMARKET RAW DATA LOGGER")
    print("="*80)
    print(f"Assets: {len(ASSET_IDS)}")
    for i, asset_id in enumerate(ASSET_IDS, 1):
        print(f"  {i}. {asset_id[:20]}...")
    print("="*80)

    # Create logger with custom settings
    logger = RawDataLogger(
        ASSET_IDS,
        data_dir=args.data_dir,
        rotation_interval=args.rotation_interval,
        auto_stop_after=args.auto_stop
    )
    logger.start()

    # Create WebSocket
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    # Give logger reference to WebSocket (for auto-stop)
    logger.ws = ws

    # Stats printer thread
    def print_stats_loop():
        while logger.running:
            time.sleep(5)  # Print stats every 5 seconds
            if logger.running:
                logger.print_stats()

    stats_thread = threading.Thread(target=print_stats_loop, daemon=True)
    stats_thread.start()

    # Run WebSocket
    try:
        ws.run_forever()
    except KeyboardInterrupt:
        print("\n\nReceived interrupt signal...")
    finally:
        logger.stop()
        ws.close()
