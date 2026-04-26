#!/usr/bin/env python3
"""CLI pro spousteni osobnich automatizaci."""

from __future__ import annotations

import argparse
import sys

from automations.core import (
    get_automation,
    import_task_modules,
    list_automations,
    load_env_file,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spoustec osobnich automatizaci")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Cesta k .env souboru, ktery se ma nacist pred spustenim ulohy.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="Vypise dostupne automatizace")

    run_parser = subparsers.add_parser("run", help="Spusti jednu automatizaci")
    run_parser.add_argument("name", help="Nazev automatizace")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    load_env_file(args.env_file)
    import_task_modules()

    if args.command == "list":
        for item in list_automations():
            description = f" - {item.description}" if item.description else ""
            print(f"{item.name}{description}")
        return 0

    if args.command == "run":
        task = get_automation(args.name)
        task.func()
        return 0

    parser.error("Neznamy prikaz")
    return 2


if __name__ == "__main__":
    sys.exit(main())

