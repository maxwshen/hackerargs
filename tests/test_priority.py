"""
    test
"""
import sys
import os
import argparse
import pytest

from util import new_args



def test_priority():
    parser = argparse.ArgumentParser()
    parser.add_argument('--default', default = 'default')

    args = new_args()
    sys.argv = ['test.py']
    args.parse_args(parser)
    assert args['default'] == 'default'

    args = new_args()
    sys.argv = ['test.py']
    args.parse_args(parser, 'tests/test.yaml')
    assert args['default'] == 'yaml'

    args = new_args()
    sys.argv = ['test.py', '--config', 'tests/test.yaml']
    args.parse_args(parser)
    assert args['default'] == 'yaml'

    args = new_args()
    sys.argv = ['test.py', '--config', 'tests/test.yaml', '--default', 'cli']
    args.parse_args(parser)
    assert args['default'] == 'cli'

    args = new_args()
    sys.argv = ['test.py', '--default', 'cli']
    args.parse_args(parser)
    assert args['default'] == 'cli'
