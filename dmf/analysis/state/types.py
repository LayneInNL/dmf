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


class PrimitiveTypes:
    NUM = -100

    BOOL = -90

    STR = -80

    BYTES = -70

    NONE = -60

    UNDEF = -50

    DICT = -40

    SET = -30

    LIST = -20

    TUPLE = -10

    FUNC = -110


class BoolObjectInfo:
    name = "Bool"
    context = PrimitiveTypes.BOOL
    address = (name, context)
    obj = (context, None)


class NoneObjectInfo:
    name = "None"
    context = PrimitiveTypes.NONE
    address = (name, context)
    obj = (context, None)


class NumObjectInfo:
    name = "Num"
    context = PrimitiveTypes.NUM
    address = (name, context)
    obj = (context, None)


class StrObjectInfo:
    name = "Empty"
    context = PrimitiveTypes.STR
    address = (name, context)
    obj = (context, None)


class BytesObjectInfo:
    name = "Bytes"
    context = PrimitiveTypes.BYTES
    address = (name, context)
    obj = (context, None)


class UndefObjectInfo:
    name = "Undef"
    context = PrimitiveTypes.UNDEF
    address = (name, context)
    obj = (context, None)


class DictObjectInfo:
    name = "Dict"
    context = PrimitiveTypes.DICT
    address = (name, context)
    obj = (context, None)


class SetObjectInfo:
    name = "Set"
    context = PrimitiveTypes.SET
    address = (name, context)
    obj = (context, None)


class ListObjectInfo:
    name = "List"
    context = PrimitiveTypes.LIST
    address = (name, context)
    obj = (context, None)


class TupleObjectInfo:
    name = "Tuple"
    context = PrimitiveTypes.TUPLE
    address = (name, context)
    obj = (context, None)


class FuncObjectInfo:
    name = "Func"
    context = PrimitiveTypes.FUNC
    address = (name, context)
    obj = (context, None)


# a mapping used in store
BUILTIN_CLASSES = (
    BoolObjectInfo,
    NoneObjectInfo,
    NumObjectInfo,
    BytesObjectInfo,
    UndefObjectInfo,
    DictObjectInfo,
    SetObjectInfo,
    ListObjectInfo,
    TupleObjectInfo,
    FuncObjectInfo,
)
# a mapping from names to addresses, used in data stack
BUILTIN_CLASS_NAMES = {a.name: a.address for a in BUILTIN_CLASSES}
