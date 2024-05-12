# hackerargs

![https://github.com/maxwshen/hackerargs/actions/workflows/python-package.yml/badge.svg]

Usage

```python

# do this in any script
from hackerargs import args

# do this anywhere
value = args.setdefault(key, default_value)

```

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
