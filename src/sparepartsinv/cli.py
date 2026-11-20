"""Command line entry: python -m sparepartsinv [--db FILE] <command>"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from . import store

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "parts.csv"


def print_parts(rows: list[sqlite3.Row]) -> None:
    """Print parts as a table."""
    print(f"{'SKU':<10}{'Name':<22}{'Qty':>5}{'Min':>5}  Location")
    for r in rows:
        print(f"{r['sku']:<10}{r['name']:<22}{r['quantity']:>5}{r['min_qty']:>5}  {r['location']}")


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(prog="sparepartsinv", description="Spare parts inventory")
    parser.add_argument("--db", default="inventory.db", help="database file (default inventory.db)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="add a new part")
    add.add_argument("sku")
    add.add_argument("name")
    add.add_argument("--qty", type=int, default=0)
    add.add_argument("--min", type=int, default=0, dest="min_qty")
    add.add_argument("--location", default="")
    for name in ("receive", "issue"):
        p = sub.add_parser(name, help=f"{name} stock")
        p.add_argument("sku")
        p.add_argument("qty", type=int)
        p.add_argument("--note", default="")
    sub.add_parser("list", help="list all parts")
    sub.add_parser("low", help="list parts at or below minimum")
    hist = sub.add_parser("history", help="show movements of one part")
    hist.add_argument("sku")
    imp = sub.add_parser("import", help="add parts from a CSV file")
    imp.add_argument("csv")
    sub.add_parser("demo", help="load the sample data into memory, issue some parts, show low stock")
    return parser


def run(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    """Execute one parsed command."""
    if args.cmd == "add":
        store.add_part(conn, args.sku, args.name, args.qty, args.min_qty, args.location)
        print(f"added {args.sku}")
    elif args.cmd in ("receive", "issue"):
        if args.qty <= 0:
            raise store.StockError("qty must be a positive number")
        sign = 1 if args.cmd == "receive" else -1
        print(f"{args.sku} now {store.move(conn, args.sku, sign * args.qty, args.note)}")
    elif args.cmd == "list":
        print_parts(store.all_parts(conn))
    elif args.cmd == "low":
        rows = store.low_stock(conn)
        print_parts(rows) if rows else print("nothing is low")
    elif args.cmd == "history":
        for r in store.history(conn, args.sku):
            print(f"{r['at']}  {r['delta']:+d}  {r['note']}")
    elif args.cmd == "import":
        print(f"imported {store.import_csv(conn, args.csv)} parts")
    elif args.cmd == "demo":
        store.import_csv(conn, str(SAMPLE))
        store.move(conn, "FLT-2025", -8, "AHU filter change")
        store.move(conn, "LED-2X4", -32, "lobby retrofit")
        print("Low stock after the demo issues")
        print_parts(store.low_stock(conn))


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    conn = store.connect(":memory:" if args.cmd == "demo" else args.db)
    try:
        run(conn, args)
    except (store.StockError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0
