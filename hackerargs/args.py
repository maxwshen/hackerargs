from __future__ import annotations
import sys
import os
from pathlib import Path
import argparse
import yaml
from typing import Any, Optional
import logging
from collections.abc import MutableMapping

from .strict_bool_yaml import StrictBoolSafeLoader
from . import argparse_access

logger = logging.getLogger('hackerargs')


def yaml_load(stream) -> dict[str, Any] | Any:
    """ Parse stream using StrictBoolSafeLoader.
        If stream is yaml-formatted string or file, then returns parsed
        dict[str -> Any] where values have inferred python types.
        If stream is string, returns it cast to inferred python type.

        Uses PyYAML parser, which largely supports YAML v1.1
        https://yaml.org/spec/1.1/
        other than *not* parsing yes/no/on/off as booleans.
    """
    return yaml.load(stream, Loader = StrictBoolSafeLoader)


def get_yaml(inputs: list[str | argparse.ArgumentParser]) -> str | None:
    def is_yaml(x: str | argparse.ArgumentParser) -> bool:
        yaml_exts = ['.yaml', '.yml']
        return type(x) == str and any(x.endswith(ye) for ye in yaml_exts)
    yaml_files = [inp for inp in inputs if is_yaml(inp)]
    if len(yaml_files) > 1:
        raise ValueError('Must provide zero or one yaml files.')
    return yaml_files[0] if len(yaml_files) != 0 else None
    
    
def get_argparser(
    inputs: list[str | argparse.ArgumentParser]
) -> argparse.ArgumentParser | None:
    is_argparser = lambda x: type(x) == argparse.ArgumentParser
    parsers = [inp for inp in inputs if is_argparser(inp)]
    if len(parsers) > 1:
        raise ValueError('Must provide zero or one ArgumentParsers.')
    return parsers[0] if len(parsers) != 0 else None


def get_priority_yaml(parse_args_yaml: str | None, argv: list[str]) -> str | None:
    """ Prioritize between yaml input to `parse_args` method,
        and --config yaml in argv, returning a single yaml file for loading.
        Returns None if neither yaml is found.
    """
    # get possible yaml from --config cli arg
    if '--config' in argv:
        cli_yaml = argv[argv.index('--config') + 1]
    else:
        cli_yaml = None

    if parse_args_yaml and not cli_yaml:
        return parse_args_yaml
    elif not parse_args_yaml and cli_yaml:
        return cli_yaml
    elif parse_args_yaml and cli_yaml:
        if parse_args_yaml != cli_yaml:
            logger.warning((
                f'Called parse_args with {parse_args_yaml}, '
                f'but using {cli_yaml} instead, from --config CLI option'
            ))
        return cli_yaml
    return None


def check_duplicate_argv_keys(argv: list[str]) -> None:
    is_key = lambda x: x.startswith('-') or x.startswith('--')
    keys = [k for k in argv if is_key(k)]
    if len(set(keys)) < len(keys):
        raise ValueError(f'Found duplicate keys in {keys=}')
    return


def get_user_no_spec_keys( 
    parser_dict: dict, 
    parser: argparse.ArgumentParser, 
    argv: list[str]
) -> list[str]:
    """ parser_dict: result from ArgumentParser.parse_known_args()
        Returns list of keys in parser_dict that the user did not specify,
        and are not positional arguments: argparser default values were
        used for these.
    """
    no_user_spec = lambda k: f'--{k}' not in argv and f'-{k}' not in argv
    positional_args = argparse_access.get_positional_keys(parser)
    return [key for key in parser_dict.keys()
            if no_user_spec(key) and key not in positional_args]


class WriteOnceDict(MutableMapping, dict):
    __getitem__ = dict.__getitem__
    __iter__ = dict.__iter__
    __len__ = dict.__len__

    def __init__(self):
        """ dict where each key can be written to only once,
            and entries cannot be deleted.

            Subclasses MutableMapping and dict, so it supports standard dict
            methods like: keys(), get(), items(), setdefault(), values().
        """
        pass

    def __getattr__(self, key: str) -> Any:
        return self[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self:
            raise KeyError(f'{key} has already been set.')
        dict.__setitem__(self, key, value)
        return

    def __delitem__(self, key: str) -> None:
        raise KeyError('Cannot delete from WriteOnceDict.')

    def setdefault(self, key: str, default_value: Any) -> Any:
        """ If key does not exist, store {key: default_value}.
            Returns value of key. Ensures that values are never overwritten.
        """
        if key not in self:
            self[key] = default_value
        return self[key]
    
    def parse_args(
        self,
        *inputs: list[str | argparse.ArgumentParser],
        argv: Optional[list[str]] = None,
    ) -> None:
        """ Parse CLI args using argparse.ArgumentParser and load YAML config.
            If argv is given, use that instead of sys.argv.

            Initialization priority
            -----------------------
            1. (Highest priority) argparse, user-specified values
            2. Unknown CLI args specified by user in --{key} {val} format
            3. YAML file. YAML provided by --config {yaml} CLI option takes
                priority over yaml_file provided as argument to parse_args.
            4. (Lowest) argparse default values for options not specified by user
            
            Usage
            -----
            - parse_args()
            - parse_args(argparse.ArgumentParser)
            - parse_args(yaml_file)
            - parse_args(yaml_file, ArgumentParser) or 
              parse_args(ArgumentParser, yaml_file)
            argv_string is a named optional parameter:
            - parse_args(argv = ['--string', 'text', '--float', '3.14'])
            - ...
            - parse_args(ArgumentParser, yaml_file,
                argv = ['--string', 'text', '--float', '3.14'])
        """
        logger.debug('f{inputs=}')
        if len(self) != 0:
            raise ValueError('hackerargs must be empty to call `parse_args`.')

        maybe_yaml = get_yaml(inputs)
        maybe_parser = get_argparser(inputs)
        if argv is None:
            argv = sys.argv[1:]
        logger.debug(f'Found {argv=}')
        check_duplicate_argv_keys(argv)

        # form argparser
        if maybe_parser is None:
            parser = argparse.ArgumentParser(allow_abbrev = False)
        else:
            parser = maybe_parser

        parser_namespace, unknown = parser.parse_known_args(argv)
        parser_dict = vars(parser_namespace)
        logger.debug(f'Found parser known dict {parser_dict}')

        no_spec_keys = get_user_no_spec_keys(parser_dict, parser, argv)
        spec_keys = [k for k in parser_dict.keys() if k not in no_spec_keys]

        logger.info((
            'hackerargs: (Priority 1 -- highest) '
            'Updating with ArgumentParser args specified by user'
        ))
        for key in spec_keys:
            value = parser_dict[key]
            # if type != str, value has type from argparse already
            self[key] = yaml_load(value) if type(value) == str else value

        logger.info((
            'hackerargs: (Priority 2) '
            'Updating with unknown CLI args specified by user'
        ))
        self.__update_with_unknown_cli_args(unknown)

        logger.info((
            'hackerargs: (Priority 3) '
            'Updating with YAML config'
        ))
        yaml_fn = get_priority_yaml(maybe_yaml, argv)
        if yaml_fn is not None:
            self.__load_yaml_setdefault(yaml_fn)

        logger.info((
            'hackerargs: (Priority 4) '
            'Updating with argparser default values, not specified by user'
        ))
        for key in no_spec_keys:
            value = parser_dict[key]
            # if type != str, value has type from argparse already
            self.setdefault(key, yaml_load(value) if type(value) == str else value)
        return

    def __load_yaml_setdefault(self, yaml_fn: str) -> None:
        logger.info(f'Loading args from {yaml_fn} ...')
        with open(yaml_fn) as f:
            yaml_args = yaml_load(f)
        for key, value in yaml_args.items():
            self.setdefault(key, value)
        return

    def __update_with_unknown_cli_args(self, unknown: list[str]) -> None:
        """ Update with unknown CLI args, of form `--{key} {val}. """
        logger.debug(f'Found {unknown=}')
        if len(unknown) % 2 != 0:
            raise ValueError((
                'Require even number of unknown arguments, but found '
                f'{unknown=}'
            ))
        for key, val in zip(unknown[0::2], unknown[1::2]):
            if not key.startswith('--'):
                raise ValueError(f'Unknown CLI {key=} must starts with --')
            self[key[2:]] = yaml_load(val)
        return

    def save_to_yaml(self, out_yaml_file: str) -> None:
        """ Saves args into yaml file.
            Create parent folders recursively if needed.
        """
        Path(os.path.dirname(out_yaml_file)).mkdir(
            parents = True, 
            exist_ok = True
        )
        with open(out_yaml_file, 'w') as f:
            yaml.dump(dict(self), f)
        logger.info(f'Saved hackerargs to {out_yaml_file}.')
        return

