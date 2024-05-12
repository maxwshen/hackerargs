"""
    test
"""
import sys
import os
import argparse
import pytest

from util import new_args


def test_positional():
    parser = argparse.ArgumentParser()
    parser.add_argument('positional', default = 'default')

    args = new_args()
    sys.argv = ['test.py']
    with pytest.raises(SystemExit):
        args.parse_args(parser)

    args = new_args()
    sys.argv = ['test.py', 'cli']
    args.parse_args(parser)
    assert args['positional'] == 'cli'

    args = new_args()
    sys.argv = ['test.py', 'cli']
    args.parse_args(parser, 'tests/test.yaml')
    assert args['positional'] == 'cli'

    args = new_args()
    sys.argv = ['test.py', 'cli', '--config', 'tests/test.yaml']
    args.parse_args(parser, 'tests/test.yaml')
    assert args['positional'] == 'cli'