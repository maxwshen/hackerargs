"""
    test
"""
import sys
import os
import argparse
import pytest

from util import new_args


def test_access():
    args = new_args()
    sys.argv = ['test.py']
    args.parse_args('tests/test.yaml')

    assert args['int'] == 42
    assert args.int == 42
    
    with pytest.raises(Exception):
        args['int'] = 0

    assert args['int'] == 42
    assert args.int == 42

    assert isinstance(args, dict)

    args.save_to_yaml('test_save.yaml')
