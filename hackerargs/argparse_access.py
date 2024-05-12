"""
    Access internal code in argparse, which can be changed at any time
"""
import argparse


def get_positional_keys(parser: argparse.ArgumentParser) -> list[str]:
    """ Get names of positional arguments from parser.
        Accesses internal code in argparse which may not be stable.
    """
    acts = parser._get_positional_actions()
    return [act.dest for act in acts]