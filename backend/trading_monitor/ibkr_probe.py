from __future__ import annotations

import argparse
import socket
from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from .config import IbkrConfig, load_config
from .ibkr import IbkrMarketDataClient, IbkrUnavailable


DEFAULT_API_PORTS = (7497, 7496, 4002, 4001)


def socket_is_open(host: str, port: int, timeout_seconds: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def candidate_ports(configured_port: int, extra_ports: Iterable[int] = DEFAULT_API_PORTS) -> List[int]:
    ports = [configured_port]
    for port in extra_ports:
        if port not in ports:
            ports.append(port)
    return ports


def first_open_port(host: str, ports: Iterable[int]) -> Optional[int]:
    for port in ports:
        if socket_is_open(host, port):
            return port
    return None


def probe_market_data(config: IbkrConfig, symbol: str) -> str:
    client = IbkrMarketDataClient(config)
    try:
        status = client.connect()
        if not status.connected:
            return f"IBKR API socket is open, but API connection failed: {status.message}"
        update = client.latest_price(symbol, datetime.now(timezone.utc))
        delay = "delayed" if update.delayed else "live"
        return f"Connected to IBKR and received {delay} market data for {update.symbol}: {update.price}"
    except IbkrUnavailable as exc:
        return f"IBKR connection failed: {exc}"
    finally:
        client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local IBKR API market-data connectivity.")
    parser.add_argument("--host", default=None, help="IBKR API host, defaults to IBKR_HOST or 127.0.0.1.")
    parser.add_argument("--port", type=int, default=None, help="IBKR API port to test first.")
    parser.add_argument("--symbol", default="VOO", help="Symbol to request for the market-data smoke test.")
    args = parser.parse_args()

    app_config = load_config()
    host = args.host or app_config.ibkr.host
    configured_port = args.port or app_config.ibkr.port
    ports = candidate_ports(configured_port)

    print(f"Checking IBKR API sockets on {host}: {', '.join(str(port) for port in ports)}")
    open_port = first_open_port(host, ports)
    if open_port is None:
        print("No IBKR API socket is listening.")
        print("Start TWS or IB Gateway, log in, enable API socket clients, and verify the socket port.")
        return

    print(f"Found listening IBKR API socket on {host}:{open_port}")
    ibkr_config = replace(app_config.ibkr, host=host, port=open_port)
    print(probe_market_data(ibkr_config, args.symbol))


if __name__ == "__main__":
    main()
