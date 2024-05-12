"""
    Maintains a global write-once dict args, accessible from other scripts.

    Usage
    -----
    In a python script, import args.
    >>> from hackerargs import args

    Steps

    1 (Optional): Init default args from yaml. Doing this instantiates
        arguments in dict with automatically inferred types. 
        A default yaml gives the user an idea of the most important 
        expected arguments.
    >>> args.init_from_yaml('args.yaml')
    
    # In main script, once:

    2. Parse args from CLI in --arg value format. 
        If args were init'd from yaml, then types are interpreted accordingly. 
        Unknown args, or when args were not init'd, infer types using
        int > float > bool > str.
        Parsing CLI args supports wandb sweeps.
    >>> args.parse_cli_args()

    3. In other scripts, access using setdefault method.
        If key is not in args, this sets args[key] = value.
    >>> parameter_value = args.setdefault(key, value)

    4. After all code has run
    >>> args.save_to_yaml(output_yaml_file)
    
    Design philosophy
    -----------------
    Handling args as a global variable has these benefits:
    + Code readability: function signatures are concise, enabling understanding
      at a higher level of abstraction
    + Easier development: To add a new argument to a function, only 1 line of
      code change is needed: just add setdefault into the function. 
      This system enables specifying values with CLI arguments without any 
      other code changes. In contrast, explicitly changing the function
      signature requires further code changes everywhere that function is called
      to support calling the function with custom values.
    
    Only using setdefault guarantees that args entries are never updated
    twice, which lets us save args to a yaml file at the end of usage
    while achieving exact reproducibility: loading that yaml file loads
    the original argument values, if the default values in code changes over
    time.
"""

import sys
import os
from pathlib import Path
import argparse
import yaml
from typing import Any, Optional
import logging

from .strict_bool_yaml import StrictBoolSafeLoader

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

    """
        Access
    """
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

    """
        Parsing
    """
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
        if '--config' in sys.argv:
            cli_yaml = sys.argv[sys.argv.index('--config') + 1]
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

        # Update with parsed args
        no_spec = lambda k: f'--{k}' not in sys.argv and f'-{k}' not in sys.argv
        for key, val in vars(args_namespace).items():
            if no_spec(key) and key in self._privatedict:
                # k, v parsed by argparser, but not specified by user,
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

