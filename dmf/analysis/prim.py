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

NOTHING = None


class PrimType:
    pass


class BoolType(PrimType):
    def __init__(self):
        pass

    def __add__(self, other):
        if isinstance(other, (BoolType, NumType)):
            return PRIM_NUM
        elif isinstance(other, (ByteType, StrType, NoneType)):
            return NOTHING
        else:
            assert False

    def __sub__(self, other):
        return self.__add__(other)

    def __mul__(self, other):
        if isinstance(other, (BoolType, NumType)):
            return PRIM_NUM
        elif isinstance(other, ByteType):
            return PRIM_BYTE
        elif isinstance(other, StrType):
            return PRIM_STR
        elif isinstance(other, NoneType):
            return NOTHING
        else:
            assert False

    def __truediv__(self, other):
        return self.__add__(other)

    def __repr__(self):
        return "bool"


class NumType(PrimType):
    def __init__(self):
        pass

    def __add__(self, other):
        if isinstance(other, (BoolType, NumType)):
            return PRIM_NUM
        elif isinstance(other, (ByteType, StrType, NoneType)):
            return NOTHING
        else:
            assert False

    def __sub__(self, other):
        return self.__add__(other)

    def __mul__(self, other):
        if isinstance(other, (BoolType, NumType)):
            return PRIM_NUM
        elif isinstance(other, ByteType):
            return PRIM_BYTE
        elif isinstance(other, StrType):
            return PRIM_STR
        elif isinstance(other, NoneType):
            return NOTHING
        else:
            assert False

    def __truediv__(self, other):
        return self.__add__(other)

    def __repr__(self):
        return "num"


class ByteType(PrimType):
    def __init__(self):
        pass

    def __add__(self, other):
        if isinstance(other, ByteType):
            return PRIM_BYTE
        elif isinstance(other, (BoolType, NumType, StrType, NoneType)):
            return NOTHING
        else:
            assert False

    def __sub__(self, other):
        if isinstance(other, (BoolType, NumType, ByteType, StrType, NoneType)):
            return NOTHING
        else:
            assert False

    def __mul__(self, other):
        if isinstance(other, (BoolType, NumType)):
            return PRIM_BYTE
        elif isinstance(other, (ByteType, StrType, NoneType)):
            return NOTHING
        else:
            assert False

    def __truediv__(self, other):
        return self.__sub__(other)

    def __repr__(self):
        return "byte"


class StrType(PrimType):
    def __init__(self):
        pass

    def __add__(self, other):
        if isinstance(other, StrType):
            return StrType
        elif isinstance(other, (BoolType, NumType, ByteType, NoneType)):
            return NOTHING
        else:
            assert False

    def __sub__(self, other):
        if isinstance(other, (BoolType, NumType, ByteType, StrType, NoneType)):
            return NOTHING
        else:
            assert False

    def __mul__(self, other):
        if isinstance(other, (BoolType, NumType)):
            return StrType
        elif isinstance(other, (ByteType, StrType, NoneType)):
            return NOTHING
        else:
            assert False

    def __truediv__(self, other):
        return self.__sub__(other)

    def __repr__(self):
        return "str"


class NoneType(PrimType):
    def __init__(self):
        pass

    def __add__(self, other):
        if isinstance(other, (BoolType, NumType, ByteType, StrType, NoneType)):
            return NOTHING
        else:
            assert False

    def __sub__(self, other):
        return self.__add__(other)

    def __mul__(self, other):
        return self.__add__(other)

    def __truediv__(self, other):
        return self.__add__(other)

    def __repr__(self):
        return "none"


PRIM_BOOL = BoolType()
PRIM_NUM = NumType()
PRIM_BYTE = ByteType()
PRIM_STR = StrType()
PRIM_NONE = NoneType()
