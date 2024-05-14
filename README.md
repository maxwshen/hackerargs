# hackerargs

![Python package testing badge](https://github.com/maxwshen/hackerargs/actions/workflows/python-package.yml/badge.svg)
![Supports python 3.9-3.12](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)


**hackerargs** minimizes new lines of code to add a configurable argument anywhere in your codebase, so you can focus on coding.

```python
# in any python file in your codebase
from hackerargs import args

class Model:
    def __init__(self):
        self.parameter = args.setdefault(key, default_value)
        # run forth and code with confidence!
        # value can be taken from CLI or yaml config if provided
```

- Hackerargs is a global, write-once-only dict. The first setting of each key is final, ensuring exact reproducibility when saving to yaml, and later loading it to rerun your script.
- We emphasize `val = setdefault(key, default_val)` as a primitive, which returns your key's value if it already exists, and setting it to default_val otherwise. No more fumbling with errors accessing missing keys. Initializing args from CLI or yaml config takes priority over runtime setdefault.

Features
- Values have python types inferred as floats, ints, strings, lists, etc. with PyYAML loader. YAML v1.1 except "on/off/yes/no" are not parsed as booleans
- Optional integration with argparse
- Works with wandb sweeps: log config using `wandb.config.update(args)`, and run sweep experiments in CLI `--{key} {val}` format.

# Installation

Hackerargs is a pip package and conda package:

```bash
pip install hackerargs
```

or
```bash
conda install mxwsn::hackerargs
conda install -c mxwsn hackerargs
```

# Initialization

Initialize hackerargs in your driver script, just like argparse:

```python
from hackerargs import args

if __name__ == '__main__':
    args.parse_args()
    main()
    args.save_to_yaml(yaml_file)
```

parse_args can be called by itself, or with a YAML config file, or argparse.ArgumentParser:

- `args.parse_args()`
- `args.parse_args('config.yaml')`
- `args.parse_args(argparse.ArgumentParser())`
- `args.parse_args(argparse.ArgumentParser(), 'config.yaml')`: The input order doesn't matter. 

### Priority
1. (Highest priority) ArgumentParser options specified by user
2. Unknown CLI options (not recognized by ArgumentParser) specified by user. These are parsed in `--{key} {val}` format. If no argparser is given, then all CLI options are parsed this way.
3. YAML config. If `--config {yaml_file}` CLI option is given, it is used instead of a yaml file given as input to parse_args() in python. As such, `--config` is a protected CLI option when using hackerargs.
4. (Lowest priority) ArgumentParser default values for options not specified by user.

As a write-once-only dict, initialized values take priority over runtime values.


### Access

Running `python train.py --string text --int 42 --float 3.14 --list [1,2]`, we have:

```python
>>> args
{'string': 'text', 'int': 42, 'float': 3.14, 'list': [1, 2]}
>>> args.setdefault('float', 1e-4)
3.14
>>> args.get('float')
3.14
>>> args['float']
3.14
>>> args.float
3.14
```

When a key might not be set, we recommend using setdefault for access.
When you're sure the key is set already, hackerargs supports .get, bracket access, and dot access.


### Compatibility with argparse

Build your own ArgumentParser, and pass it to hackerarg:

```python
import argparse
from hackerargs import args

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--example', description = 'Example argument')
    parser.add_argument('--flag', action = 'store_true')
    # ...

    args.parse_args(parser)               # Uses parser on CLI args
```

hackerargs will first use your ArgumentParser to parse known arguments,
then parse unknown CLI arguments in `--{key} {val}` format.

Running `python example.py --example text --unknown 1`, we get:

```python
args = {'example': 'text', 'flag': False, 'unknown': 1}
```

Supporting argparse lets you create help messages for your scripts easily.
