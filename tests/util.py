import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from hackerargs.args import WriteOnceDict


def new_args():
    return WriteOnceDict()
