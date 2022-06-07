#  Copyright 2022 Layne Liu
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from __future__ import annotations


class BinOp:
    def binop(self, dunder_method, other):
        try:
            method = getattr(self.internal, dunder_method)
        except AttributeError:
            raise

        try:
            res = method(other.internal)
        except TypeError:
            raise
        else:
            res_type_name = res.__class__.__name__
            if res_type_name in real2abstract:
                return real2abstract[res_type_name]
            else:
                assert False


index = -1


def index_generator():
    global index
    temp = index
    index -= 1
    return temp


class Int(BinOp):
    uuid = index_generator()
    internal = 1

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class Float(BinOp):
    uuid = index_generator()
    internal = 1.0

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class Complex(BinOp):
    uuid = index_generator()
    internal = 1j

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class Bool(BinOp):
    uuid = index_generator()
    internal = True

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class NoneType(BinOp):
    uuid = index_generator()
    internal = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class Str(BinOp):
    uuid = index_generator()
    internal = ""

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class Bytes(BinOp):
    uuid = index_generator()
    internal = b""

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class ListType:
    uuid = index_generator()
    internal = []

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class TupleType:
    uuid = index_generator()
    internal = ()

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class SetType:
    uuid = index_generator()
    internal = set()

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class DictType:
    uuid = index_generator()
    internal = {}

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class SuperType:
    uuid = index_generator()
    internal = super

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__name__


BUILTIN_TYPES = (Int, Float, Bool, NoneType, Str, Bytes)
real2abstract = {
    "int": Int(),
    "float": Float(),
    "bool": Bool(),
    "NoneType": NoneType(),
    "str": Str(),
    "bytes": Bytes(),
}
