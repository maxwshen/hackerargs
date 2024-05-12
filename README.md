# hackerargs

![Python package testing badge](https://github.com/maxwshen/hackerargs/actions/workflows/python-package.yml/badge.svg)
![Supports python 3.9-3.12](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)

**hackerargs** minimizes new lines of code to add a new argument, command-line option,
or config option anywhere in your codebase.
Its design enables you to start hacking, prototyping, writing code,
and focus on experiments without thinking about argument handling.
By handling arguments for you, you can write cleaner code.

```python
# in your driver script
from hackerargs import args

if __name__ == '__main__':
    args.parse_args()               # parses command-line arguments
    main()
    args.save_to_yaml(yaml_file)
```

```python
# in any python script/file, anywhere in your codebase
from hackerargs import args

parameter_value = args.setdefault(key, default_value)
```

**hackerargs** acts as a global write-once-only dict after initialization.
Hackerargs is built around `value = args.setdefault(key, default_value)`,
which returns the value of the specified key.
If the key does not exist, its value is set to default_value.
setdefault is a standard method on python dicts, albeit relatively unknown.
Its use in hackerargs ensures that populated args can be saved to file at the end,
and reloading later for reproducibility.

### Easy CLI options

```bash
python train.py --lr 1e-1
```

```python
from hackerargs import args

if __name__ == '__main__':
    args.parse_args()               # parses command-line arguments
    lr = args.setdefault('lr', 1e-3)
    # lr = 1e-1 (type = float), already specified by user on command-line
```


### Type inference

```bash
python example.py --none [~,null] --bool [true,false,on,off,yes,no] --int 42 --float 3.14159 --list [LITE,RES_ACID,SUS_DEXT]
```

```python
from hackerargs import args

if __name__ == '__main__':
    args.parse_args()               # parses command-line arguments
```

```python
args = {'none': [None, None], 'bool': [True, False, 'on', 'off', 'yes', 'no'], 'int': 42, 'float': 3.14159, 'list': ['LITE', 'RES_ACID', 'SUS_DEXT']}
```

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
