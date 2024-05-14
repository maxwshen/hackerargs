"""
    test
"""
import sys
import os
import argparse
import pytest
import logging

from util import new_args

logging.basicConfig(level = logging.DEBUG)



def test_priority():
    parser = argparse.ArgumentParser()
    parser.add_argument('--default', default = 'default')

    args = new_args()
    args.parse_args(parser, argv = [])
    assert args['default'] == 'default'

    args = new_args()
    args.parse_args(parser, 'tests/test.yaml', argv = [])
    assert args['default'] == 'yaml'

    args = new_args()
    args.parse_args(parser, argv = ['--config', 'tests/test.yaml'])
    assert args['default'] == 'yaml'

    args = new_args()
    args.parse_args(parser, argv = ['--config', 'tests/test.yaml', '--default', 'cli'])
    assert args['default'] == 'cli'

    args = new_args()
    args.parse_args(parser, argv = ['--default', 'cli'])
    assert args['default'] == 'cli'


if __name__ == '__main__':
    test_priority()