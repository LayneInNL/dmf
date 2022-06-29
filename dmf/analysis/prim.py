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


def _index_generator():
    index = -1

    def generate_next_one():
        nonlocal index
        temp = index
        index -= 1
        return temp

    return generate_next_one


index_generator = _index_generator()


class Int(BinOp):
    internal = 1
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class Float(BinOp):
    internal = 1.0
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class Complex(BinOp):
    internal = 1j
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class Bool(BinOp):
    internal = True
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class NoneType(BinOp):
    internal = None
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class Str(BinOp):
    internal = ""
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class Bytes(BinOp):
    internal = b""
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class ListType:
    internal = []
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class TupleType:
    internal = ()
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class SetType:
    internal = set()
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class DictType:
    internal = {}
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return self.internal.__class__.__name__


class SuperType:
    internal = super
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = index_generator()
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

magic1 = ("__new__", "__init__", "__del__")
magic2 = (
    "__lt__",
    "__le__",
    "__eq__",
    "__ne__",
    "__gt__",
    "__ge__",
)
magic3 = (
    "__pos__",
    "__neg__",
    "__abs__",
    "__invert__",
    "__round__",
    "__floor__",
    "__ceil__",
    "__trunc__",
)
magic4 = (
    "__add__",
    "__sub__",
    "__mul__",
    "__floordiv__",
    "__div__",
    "__truediv__",
    "__mod__",
    "__divmod__",
    "__pow__",
    "__lshift__",
    "__rshift__",
    "__and__",
    "__or__",
    "__xor__",
)

magic5 = (
    "__radd__",
    "__rsub__",
    "__rmul__",
    "__rfloordiv__",
    "__rdiv__",
    "__rtruediv__",
    "__rmod__",
    "__rdivmod__",
    "__rpow__",
    "__rlshift__",
    "__rrshift__",
    "__rand__",
    "__ror__",
    "__rxor__",
)

magic6 = (
    "__iadd__",
    "__isub__",
    "__imul__",
    "__ifloordiv__",
    "__idiv__",
    "__itruediv__",
    "__imod__",
    "__ipow__",
    "__ilshift__",
    "__irshift__",
    "__iand__",
    "__ior__",
    "__ixor__",
)
magic7 = (
    "__int__",
    "__long__",
    "__float__",
    "__complex__",
    "__oct__",
    "__hex__",
    "__index__",
    "__trunc__",
    "__coerce__",
)
magic8 = (
    "__str__",
    "__repr__",
    "__unicode__",
    "__format__",
    "__hash__",
    "__nonzero__",
    "__dir__",
    "__sizeof__",
    "__bool__",
)
magic9 = (
    "__getattr__",
    "__setattr__",
    "__delattr__",
    "__getattribute__",
)
magic10 = (
    "__len__",
    "__getitem__",
    "__setitem__",
    "__delitem__",
    "__iter__",
    "__reversed__",
    "__contains__",
    "__missing__",
)
magic11 = ("__instancecheck__", "__subclasscheck__")
magic12 = ("__call__",)
magic13 = ("__enter__", "__exit__")
magic14 = ("__get__", "__set__", "__delete__")
magic15 = ("__copy__", "__deepcopy__")
