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


class Int(BinOp):
    internal = 1

    def __repr__(self):
        return self.internal.__class__.__name__


class Float(BinOp):
    def __init__(self):
        self.internal = 1.0

    def __repr__(self):
        return self.internal.__class__.__name__


class Bool(BinOp):
    def __init__(self):
        self.internal = True

    def __repr__(self):
        return self.internal.__class__.__name__


class NoneType(BinOp):
    def __init__(self):
        self.internal = None

    def __repr__(self):
        return self.internal.__class__.__name__


class Str(BinOp):
    def __init__(self):
        self.internal = ""

    def __repr__(self):
        return self.internal.__class__.__name__


class Bytes(BinOp):
    def __init__(self):
        self.internal = b""

    def __repr__(self):
        return self.internal.__class__.__name__


PRIM_INT = Int()
PRIM_INT_ID = id(PRIM_INT)
PRIM_FLOAT = Float()
PRIM_FLOAT_ID = id(PRIM_FLOAT)
PRIM_BOOL = Bool()
PRIM_BOOL_ID = id(PRIM_BOOL)
PRIM_NONE = NoneType()
PRIM_NONE_ID = id(PRIM_NONE)
PRIM_STR = Str()
PRIM_STR_ID = id(PRIM_STR)
PRIM_BYTES = Bytes()
PRIM_BYTES_ID = id(PRIM_BYTES)

BUILTIN_TYPES = (Int, Float, Bool, NoneType, Str, Bytes)
real2abstract = {
    "int": PRIM_INT,
    "float": PRIM_FLOAT,
    "bool": PRIM_BOOL,
    "NoneType": PRIM_NONE,
    "str": PRIM_STR,
    "bytes": PRIM_BYTES,
}
