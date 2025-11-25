#!/usr/bin/env python3
"""Top-level CLI dispatcher for cicada tools."""
import argparse
import importlib

COMMAND_MODULES = {
	"sign": "sign",
	"extract": "extract",
	"verify": "verify",
}

def main(argv: list[str] | None = None):
	parser = argparse.ArgumentParser(description="Cicada CLI.")
	parser.add_argument("command", choices=COMMAND_MODULES.keys(), help="Subcommand to run.")
	parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments forwarded to the subcommand.")
	ns = parser.parse_args(argv)
	module_name = COMMAND_MODULES[ns.command]
	module = importlib.import_module(module_name)
	sub_args = ns.args
	if sub_args and sub_args[0] == "--":
		sub_args = sub_args[1:]
	module.main(sub_args)

if __name__ == "__main__":
	main()
