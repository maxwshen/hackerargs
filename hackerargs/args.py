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
from typing import Any
import textwrap
import logging

from .strict_bool_yaml import StrictBoolSafeLoader

logger = logging.getLogger('hackerargs')


def yaml_load(stream) -> dict[str, object] | object:
    """ Parse stream using StrictBoolSafeLoader.
        If stream is yaml-formatted string or file, then returns parsed
        dict[str -> object] where objects have inferred python types.
        If stream is string, returns an object with inferred python type.

        Uses PyYAML parser, which largely supports YAML v1.1
        https://yaml.org/spec/1.1/
        other than *not* parsing yes/no/on/off as booleans.
    """
    return yaml.load(stream, Loader = StrictBoolSafeLoader)


class WriteOnceDict:
    def __init__(self):
        self._privatedict = dict()
        self._inited_from_yaml = False
        self._updated_with_cli = False
        logger.warning('test warning')

    def __contains__(self, key: str) -> bool:
        return bool(key in self._privatedict)

    def __repr__(self) -> str:
        return str(self._privatedict)
    
    def __getitem__(self, key: str) -> Any:
        return self._privatedict[key]
    
    def __getattr__(self, key: str) -> Any:
        return self._privatedict[key]

    def __setattr__(self, key: str, value: Any) -> Any:
        if '_privatedict' in dir(self) and key in self._privatedict:
            raise KeyError((
                'Attempting to set class variable with same name '
                'as key in WriteOnceDict.'
            ))
        super().__setattr__(key, value)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self._privatedict:
            raise KeyError('Write-once only dict')
        self._privatedict[key] = value

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

    """
        Parsing
    """
    def init_from_yaml(self, yaml_file: str) -> None:
        """ Load typed arguments from yaml file.
            If --config is specified in CLI args, read from that file.
            Otherwise, use yaml_file.
            Only callable once.
        """
        if self._inited_from_yaml or self._updated_with_cli:
            error = f'Can only init from yaml once, before parsing CLI args.'
            logger.error(error)
            raise Exception(error)

        cli_args = sys.argv
        if '--config' in cli_args:
            yaml_fn = cli_args[cli_args.index('--config') + 1]
        else:
            yaml_fn = yaml_file

        logger.info(f'Reading arguments from {yaml_fn} ...')
        with open(yaml_fn) as f:
            args = yaml_load(f)

        if len(self._privatedict) != 0:
            raise ValueError((
                'Expected empty internal args.'
                'init_from_yaml must be called before any other arguments are set.'
            ))

        self._privatedict = args
        self._inited_from_yaml = True
        return

    def parse_cli_args(
        self, 
        parser: argparse.ArgumentParser | None = None
    ) -> None:
        """ Parse python command-line arguments.
            Only callable once. 
            Value types are obtained from yaml loader, or inferred for
            unknown args.
        """
        if parser is None:
            parser = argparse.ArgumentParser(allow_abbrev = False)
            parser.add_argument(f'--config', type = str)
        for arg, val in self._privatedict.items():
            parser.add_argument(f'--{arg}', default = val, type = type(val))

        logger.info('Updating arguments with command-line options ...')
        args_namespace, unknown = parser.parse_known_args()
        self._privatedict.update(vars(args_namespace))
        self.__update_with_unknown_cli_args(unknown)

        self._updated_with_cli = True
        return

    def __update_with_unknown_cli_args(self, unknown: list[str]) -> None:
        """ Update args with unknown CLI args, of form --key val.
            Value types are inferred.
        """
        if len(unknown) % 2 != 0:
            raise ValueError('Require even number of unknown arguments')
        for i in range(len(unknown) // 2):
            key = unknown[i * 2]
            val = unknown[i * 2 + 1]

            if key[:-2] != '--':
                raise ValueError(
                    f'Expected keys to start with --, but {key} does not'
                )
            trimmed_key = key[2:]

            self._privatedict[trimmed_key] = yaml_load(val)
        return

    def save_to_yaml(self, out_yaml_file: str) -> None:
        """ Saves args into yaml file.
            Create parent folders recursively if needed.
        """
        logger.info(f'Saved args yaml to {out_yaml_file}.')
        Path(os.path.dirname(out_yaml_file)).mkdir(
            parents = True, 
            exist_ok = True
        )
        with open(out_yaml_file, 'w') as f:
            yaml.dump(self._privatedict, f)
        return

