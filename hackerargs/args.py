import sys
import os
from pathlib import Path
import argparse
import yaml
from typing import Any, Optional, Union
import logging

from .strict_bool_yaml import StrictBoolSafeLoader
from . import argparse_access

logger = logging.getLogger('hackerargs')


def yaml_load(stream) -> Union[dict[str, Any], Any]:
    """ Parse stream using StrictBoolSafeLoader.
        If stream is yaml-formatted string or file, then returns parsed
        dict[str -> Any] where values have inferred python types.
        If stream is string, returns it cast to inferred python type.

        Uses PyYAML parser, which largely supports YAML v1.1
        https://yaml.org/spec/1.1/
        other than *not* parsing yes/no/on/off as booleans.
    """
    return yaml.load(stream, Loader = StrictBoolSafeLoader)


class WriteOnceDict:
    def __init__(self):
        self._privatedict = dict()

    def __contains__(self, key: str) -> bool:
        return bool(key in self._privatedict)

    def __repr__(self) -> str:
        return str(self._privatedict)
    
    def __getitem__(self, key: str) -> Any:
        return self._privatedict[key]
    
    def __getattr__(self, key: str) -> Any:
        return self._privatedict[key]

    def __setattr__(self, key: str, value: Any) -> None:
        if '_privatedict' in dir(self) and key in self._privatedict:
            raise KeyError((
                'Attempting to set class variable with same name '
                'as key in WriteOnceDict.'
            ))
        super().__setattr__(key, value)
        return

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self._privatedict:
            raise KeyError('Write-once only dict')
        self._privatedict[key] = value
        return

    def __delitem__(self, key: str) -> None:
        raise KeyError('Cannot delete items in write-once only dict')

    def get(self, key: str) -> Any:
        return self._privatedict[key]

    def setdefault(self, key: str, default_value: Any) -> Any:
        """ If key is not in args, set args[key] = default_value.
            Then return args[key].
            Ensures that values are never overwritten.
        """
        if key not in self._privatedict:
            self._privatedict[key] = default_value
        return self._privatedict[key]
    
    def keys(self):
        return self._privatedict.keys()

    def items(self):
        return self._privatedict.items()

    def parse_args(self, *inps: list[str]) -> None:
        """ Parse args from sys.argv, and optional inputs
            config_yaml, ArgumentParser.
            When --conflig cli arg is set, prioritizes that yaml file.

            Usage
            -----
            parse_args()
                If --config {yaml_file} is set, loads that yaml first.
                Then, parses CLI args in `--{key} {val}` format,
                updating hackerargs.

            parse_args(ArgumentParser)
                If --config {yaml_file} is set, loads that yaml first.
                Calls ArgumentParser.parse_args(), and uses output to
                update hackerargs. Then parses unknown CLI args in
                `--{key} {val}` format, updating hackerargs.
            
            parse_args(yaml_file)
                If no --config CLI option is set, loads from yaml_file first.
                Otherwise, uses --config yaml instead, and raises a warning.
                Then, parses CLI args in `--{key} {val}` format,
                updating hackerargs.
            
            parse_args(yaml_file, ArgumentParser) or 
            parse_args(ArgumentParser, yaml_file)
                If no --config CLI option is set, loads from yaml_file first.
                Otherwise, uses --config yaml instead, and raises a warning.
                Calls ArgumentParser.parse_args(), and uses output to
                update hackerargs. Then parses unknown CLI args in
                `--{key} {val}` format, updating hackerargs.
        """
        if len(self._privatedict) != 0:
            raise ValueError((
                'Expected empty hackerargs. Do not set anything in hackerargs '
                'before calling `parse_args`.'
            ))

        def is_yaml(x: Any) -> bool:
            return type(x) == str and (x.endswith('.yaml') or x.endswith('.yml'))
        yaml_files = [inp for inp in inps if is_yaml(inp)]
        if len(yaml_files) > 1:
            raise ValueError('Must provide zero or one yaml files.')
        maybe_yaml = yaml_files[0] if len(yaml_files) != 0 else None
        
        parsers = [inp for inp in inps if type(inp) == argparse.ArgumentParser]
        if len(parsers) > 1:
            raise ValueError('Must provide zero or one ArgumentParsers.')
        maybe_parser = parsers[0] if len(parsers) != 0 else None

        # find possible yaml file from --config cli arg
        argv = sys.argv
        if '--config' in argv:
            cli_yaml = argv[argv.index('--config') + 1]
        else:
            cli_yaml = None

        # init from yaml
        if maybe_yaml and not cli_yaml:
            self.__init_from_yaml(maybe_yaml)
        elif not maybe_yaml and cli_yaml:
            self.__init_from_yaml(cli_yaml)
        elif maybe_yaml and cli_yaml:
            if maybe_yaml != cli_yaml:
                logger.warning((
                    f'Called parse_args with {maybe_yaml}, '
                    f'but using {cli_yaml} instead, from --config CLI option'
                ))
            self.__init_from_yaml(cli_yaml)

        self.__parse_cli_args(maybe_parser)
        return

    def __init_from_yaml(self, yaml_fn: str) -> None:
        logger.info(f'Loading hackerargs from {yaml_fn} ...')
        with open(yaml_fn) as f:
            args = yaml_load(f)
        self._privatedict = args
        return

    def __parse_cli_args(
        self, 
        parser: Optional[argparse.ArgumentParser] = None
    ) -> None:
        """ Parse command-line arguments, updating hackerargs.
            If ArgumentParser is given, use it to parse sys.argv first.
            Unknown args must follow `--{key} {val}` format, and values
            have types inferred by yaml loader.
        """
        if parser is None:
            parser = argparse.ArgumentParser(allow_abbrev = False)

        logger.info('Updating arguments with command-line options ...')
        args_namespace, unknown = parser.parse_known_args()
        args_dict = vars(args_namespace)

        positional_args = argparse_access.get_positional_keys(parser)

        # Update with parsed args
        argv = sys.argv
        no_spec = lambda k: f'--{k}' not in argv and f'-{k}' not in argv
        logger.debug(f'argparse found {args_dict.items()=}')
        for key, val in args_dict.items():
            if (no_spec(key)
                and key in self._privatedict
                and key not in positional_args
            ):
                # k, v parsed by argparser, but not specified by user as
                # optional arg, and not as positional arg,
                # means default value must have been used
                logger.info((
                    f'argparse attempting to use default for {key=} '
                    f'(not specified by user), but {key=} is in hackerargs '
                    'already. No update made: yaml file takes priority.'
                ))
                continue

            if type(val) == str:
                self._privatedict[key] = yaml_load(val)
            else:
                # val type parsed with argparse
                self._privatedict[key] = val

        self.__update_with_unknown_cli_args(unknown)
        return

    def __update_with_unknown_cli_args(self, unknown: list[str]) -> None:
        """ Update with unknown CLI args, of form `--{key} {val}. """
        logger.debug(f'Found {unknown=}')
        if len(unknown) % 2 != 0:
            raise ValueError('Require even number of unknown arguments')
        seen_keys = set()
        for i in range(len(unknown) // 2):
            key = unknown[i * 2]
            val = unknown[i * 2 + 1]

            if key[:2] != '--':
                raise ValueError(
                    f'Keys must start with --, but {key=} does not'
                )
            if key in seen_keys:
                raise ValueError(f'Duplicate found: {key=}')
            seen_keys.add(key)

            trimmed_key = key[2:]
            self._privatedict[trimmed_key] = yaml_load(val)
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
            yaml.dump(self._privatedict, f)
        logger.info(f'Saved hackerargs to {out_yaml_file}.')
        return

