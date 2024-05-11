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

from loguru import logger
import sys
import argparse, yaml
from typing import Any, Union
import textwrap


class GlobalWriteOnceDict:
    def __init__(self):
        self._privatedict = dict()
        self._got_args = False
        self._updated_with_cli = False
    
    """
        Access
    """
    def get(self, key: str) -> Any:
        return self._privatedict[key]

    def __getitem__(self, key: str) -> Any:
        """ Get with square brackets. Not recommended; use get() instead. """
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        """ Overrides 'in' operator. """
        return bool(key in self._privatedict)

    def __repr__(self) -> str:
        return str(self._privatedict)

    def setdefault(self, key: str, default_value: Any) -> Any:
        """ If key is not in args, set args[key] = default_value.
            Then return args[key].
            Ensures that values are never overwritten.
        """
        if key not in self._privatedict:
            self._privatedict[key] = default_value
        return self._privatedict[key]

    def setfirst(self, key: str, value: Any) -> None:
        """ Requires that key is not in args. Set args[key] = value. """
        assert key not in self._privatedict, 'Cannot overwrite {key}.'
        self._privatedict[key] = value
        return value

    def assert_contains(self, key: str, value_not: str = '') -> bool:
        assert key in self._privatedict, \
            f'Error: {key} not in args'
        assert self.get(key) != value_not, \
            f'Error: arg value of "{key}" cannot be "{value_not}". ' + \
            'Specify a different value in yaml or using command line.'
        return bool(key in self._privatedict)

    def assert_not_in(self, key: str) -> bool:
        assert key not in self._privatedict, \
            f'Error: {key} is in args, but assertion expected it to not be'
        return bool(key not in self._privatedict)

    """
        Parsing
    """
    def add_help(self, description: str) -> None:
        cli_args = sys.argv
        if '-h' in cli_args or '--help' in cli_args:
            print(textwrap.dedent(description))
            exit()
        return

    def init_from_yaml(self, default_yaml_fn: str) -> None:
        """ Read default typed arguments from yaml file, and set to privatedict.
            If --options_yaml is specified in CLI args, read from that file.
            Otherwise, use default_yaml_fn.
            Only callable once.
        """
        if self._got_args or self._updated_with_cli:
            error = f'Can only init from yaml once, before parsing CLI args.'
            logger.error(error)
            raise Exception(error)

        cli_args = sys.argv
        if '--options_yaml' in cli_args:
            yaml_fn = cli_args[cli_args.index('--options_yaml') + 1]
        else:
            yaml_fn = default_yaml_fn

        logger.info(f'Reading arguments from {yaml_fn} ...')
        with open(yaml_fn) as f:
            args = yaml.load(f, Loader = yaml.FullLoader)
        assert len(self._privatedict) == 0, 'Expected empty internal args'
        self._privatedict = args
        self._got_args = True
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
        if self._updated_with_cli:
            error = f'Attempted to update args from CLI more than once.'
            logger.error(error)
            raise Exception(error)

        if parser is None:
            parser = argparse.ArgumentParser(allow_abbrev = False)
            parser.add_argument(f'--options_yaml', type = str)
        for arg, val in self._privatedict.items():
            parser.add_argument(f'--{arg}', default = val, type = type(val))

        logger.info('Updating arguments with python command-line options ...')
        args_namespace, unknown = parser.parse_known_args()
        self._privatedict.update(vars(args_namespace))
        self.__update_with_unknown_cli_args(unknown)

        self._updated_with_cli = True
        return

    def __update_with_unknown_cli_args(self, unknown: list[str]) -> None:
        """ Update args with unknown CLI args, of form --key val.
            Value types are inferred.
        """
        assert len(unknown) % 2 == 0, 'Require even num. of unknown arg terms'
        for i in range(len(unknown) // 2):
            key = unknown[i * 2]
            val = unknown[i * 2 + 1]
            assert key[:2] == '--'
            trimmed_key = key[2:]
            self.setfirst(trimmed_key, self.infer_type(val))
        return

    def infer_type(self, val: str) -> int | float | None | bool | str:
        """ Infers type, prioritizing int > float > None > bool > str. """
        try:
            val = float(val)
            if val // 1 == val:
                return int(val)
            return val
        except ValueError:
            if val == 'None':
                return None
            elif val == 'True':
                return True
            elif val == 'False':
                return False
            return val

    def update_with_train_yaml(
        self, 
        arg_prefixes: list[str] = ['ft.', 'net.']
    ) -> None:
        """ Update predict args with train yaml. Use this when loading a 
            trained checkpoint, with the training yaml, to ensure that model
            hyperparameters are correctly set.
            Seeks args with protected prefixes, default: ft. and net.
        """
        assert self._updated_with_cli
        assert self.get('stages') == 'predict'
        assert 'train_yaml' in self

        yaml_fn = self.get('train_yaml')
        has_prefix = lambda key: any(key[:len(pf)] == pf for pf in arg_prefixes)

        logger.info(f'Reading training args from {yaml_fn} ...')
        with open(yaml_fn) as f:
            args = yaml.load(f, Loader=yaml.FullLoader)

        for key, val in args.items():
            if has_prefix(key):
                self.setfirst(key, val)
                logger.info(f'\t{key}, {val}')
        return

    def save_to_yaml(self, out_yaml_file: str) -> None:
        """ Saves args into yaml file.

            Intended usage accesses args in scripts using
            param_val = args.setdefault(key, value)
            which guarantees that args entries are never updated twice.
            When this implicit contract holds, saving args to a yaml file
            at the end of a script will let us exactly reproduce its behavior
            by loading the yaml args and rerunning the script, even if
            the default values changed in the script. 
        """
        logger.info(f'Saved args yaml to {out_yaml_file}.')
        with open(out_yaml_file, 'w') as f:
            yaml.dump(self._privatedict, f)
        return


args = GlobalWriteOnceDict()