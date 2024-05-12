"""
    Override pyyaml parsing of booleans:
    do not interpret on/off/yes/no as bools.
    https://stackoverflow.com/a/74150752/7815477
"""

import yaml
from yaml.loader import Reader, Scanner, Parser, Composer, SafeConstructor, Resolver


class StrictBoolSafeResolver(Resolver):
    pass


# remove resolver entries for On/Off/Yes/No
for ch in "OoYyNn":
    if len(StrictBoolSafeResolver.yaml_implicit_resolvers[ch]) == 1:
        del StrictBoolSafeResolver.yaml_implicit_resolvers[ch]
    else:
        StrictBoolSafeResolver.yaml_implicit_resolvers[ch] = [
            x for x in StrictBoolSafeResolver.yaml_implicit_resolvers[ch]
            if x[0] != 'tag:yaml.org,2002:bool'
        ]


class StrictBoolSafeLoader(
    Reader, 
    Scanner, 
    Parser, 
    Composer, 
    SafeConstructor, 
    StrictBoolSafeResolver
):
    def __init__(self, stream):
        """ Custom yaml loader that does not interpret on/off/yes/no
            as booleans.
        """
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        SafeConstructor.__init__(self)
        StrictBoolSafeResolver.__init__(self)