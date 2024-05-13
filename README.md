# hackerargs

![Python package testing badge](https://github.com/maxwshen/hackerargs/actions/workflows/python-package.yml/badge.svg)
![Supports python 3.9-3.12](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)


**hackerargs** minimizes new lines of code to add a new argument, command line option,
or config anywhere in your codebase.
Its design enables you to start hacking, prototyping, writing code,
and focus on experiments while spending zero time thinking about argument handling.
Once initialized by parsing command line arguments in `--{key} {val}` format, 
and/or loading from YAML, hackerargs acts as a global, write-once-only dict,
accessible anywhere in your codebase with `from hackerargs import args`.
Hackerargs automatically infers python object types, saves to YAML enabling
exact reproducibility, optionally integrates with argparse, and works smoothly with wandb sweeps.

Hackerargs' philosophy is "build first, document later": it does not force you
to make arguments discoverable and well-documented. To do so, we recommend
using argparse to build help messages and descriptions of key arguments, and
sharing YAML config files. 

# Installation
```bash
pip install hackerargs
```

# Usage

```python
# in your driver script
from hackerargs import args

if __name__ == '__main__':
    args.parse_args()               # parses command-line args in --{key} val format
    main()
    args.save_to_yaml(yaml_file)
```

```python
# in any python script/file, anywhere in your codebase
from hackerargs import args

class Model:
    def __init__(self):
        self.parameter = args.setdefault(key, default_value)
```

**hackerargs** acts as a global write-once-only dict after initialization.
Hackerargs is built around `value = args.setdefault(key, default_value)`,
which returns the value of the specified key if set already.
If the key does not exist, its value is first set to default_value.
setdefault is a standard method on python dicts, albeit relatively unknown.

We recommend mainly using setdefault:
- Write code thinking forward, not backward: Once you call setdefault, you're guaranteed to have a reasonable value, set from the command line, yaml config, or the default value. Run forth and use it.
- Exact reproducibility: A write-once-only dict ensures that running the script and saving populated args to yaml, enables reloading that yaml config to rerun the script with the exact same argument settings.


### Easy CLI options

```python
from hackerargs import args

if __name__ == '__main__':
    args.parse_args()   # parses command line args in --{key} val format
    lr = args.setdefault('lr', 1.0e-3)
```

If we run this script as `python train.py --lr 1.0e-1`, then we get:

```python
args = {'lr': 0.1}
```

`lr` was first specified by the user on the command line, and parsed into args, so setdefault defers to that. This lets you easily set up wandb sweeps. 


### Access

```python
>>> args.setdefault('lr', 1e-4)
0.1
>>> args.get('lr')
0.1
>>> args['lr']
0.1
>>> args.lr
0.1
```

When a key might not be set, we recommend using setdefault for access.
When you're sure the key is set already, hackerargs supports .get, bracket access, and dot access.


### Type inference & loading from YAML
```yaml
string: text
none: [~, null]
bool: [true, false, on, off]
int: 42   # comment on int
float: 3.14159
list: [LITE, RES_ACID, SUS_DEXT]
```

Command line:
- `python example.py --config config_yaml_file`: When `args.parse_args()` is called, initialize args with yaml_file. `--config` is a protected command-line option.

In python:
- `args.parse_args(config_yaml_file)`: Initialize using yaml file, then parse CLI options in `--{key} {val}` format.

Equivalent to:
- `python example.py --string text --none [~,null] --bool [true,false,on,off,yes,no] --int 42 --float 3.14159 --list [LITE,RES_ACID,SUS_DEXT]` and calling `args.parse_args()`.

```python
args = {
    'string': 'text', 
    'none': [None, None], 
    'bool': [True, False, 'on', 'off', 'yes', 'no'],
    'int': 42, 
    'float': 3.14159, 
    'list': ['LITE', 'RES_ACID', 'SUS_DEXT']
}
```

Hackerargs infers types using PyYAML's loader, which follows YAML v1.1.
The exception is we do *not* infer yes/no/on/off as booleans, which was removed
in YAML v1.2.


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


### Priority during initialization

Hackerargs can be initialized with a YAML config file, argparser, and unknown command-line arguments in `--{key} {val}` format. 
During initialization, the order of priority is:

1. (Lowest priority) argparse providing default values, when user does not specify
2. YAML config
3. (Highest priority) Command-line arguments specified by user

After initialization, setdefault cannot overwrite existing keys, and only write to new keys.
Using setdefault prioritizes existing keys either from initialization or the earliest call of setdefault.

Initialization can be called with a mix of a YAML config file and/or argparser, using:

On the command line:
- `python train.py --config yaml_file`: When `args.parse_args()` is called, initialize args with yaml_file. `--config` is a protected command-line option.

In python:
- `args.parse_args()`: Initialize by parsing command-line options in `--{key} {val}` format.
- `args.parse_args(yaml_file)`: Initialize using yaml file, then parse CLI options in `--{key} {val}` format.
- `args.parse_args(argparser)`: Initialize using argparser to parse first, then parse remaining CLI options in `--{key} {val}` format.
- `args.parse_args(argparser, yaml_file)`: Initialize using yaml file and ArgumentParser, then parse remaining CLI options in `--{key} {val}` format.
- `args.parse_args(yaml_file, argparser)`: Initialize using yaml file and ArgumentParser, then parse remaining CLI options in `--{key} {val}` format.

<!-- 
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
time. -->
