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
    NUM_NEGATIVE = -100
    NUM_ZERO = -99
    NUM_NEG_ZERO = -98
    NUM_POSITIVE = -97
    NUM_POS_ZERO = -96
    NUM_POS_ZERO_NEG = -95

    BOOL_FALSE = -90
    BOOL_TRUE = -89

    STR_EMPTY = -80
    STR_NON_EMPTY = -79

    BYTES = -70

    NONE = -60

    UNDEF = -50


class BoolFalseObjectAddress:
    name = "False"
    context = PrimitiveTypes.BOOL_FALSE
    address = (name, context)
    obj = (context, None)


class BoolTrueObjectAddress:
    name = "True"
    context = PrimitiveTypes.BOOL_TRUE
    address = (name, context)
    obj = (context, None)


class NoneObjectAddress:
    name = "None"
    context = PrimitiveTypes.NONE
    address = (name, context)
    obj = (context, None)


class NumNegObjectAddress:
    name = "Negative"
    context = PrimitiveTypes.NUM_NEGATIVE
    address = (name, context)
    obj = (context, None)


class NumZeroObjectAddress:
    name = "Zero"
    context = PrimitiveTypes.NUM_ZERO
    address = (name, context)
    obj = (context, None)


class NumNegZeroObjectAddress:
    name = "NegZero"
    context = PrimitiveTypes.NUM_NEG_ZERO
    address = (name, context)
    obj = (context, None)


class NumPosObjectAddress:
    name = "Positive"
    context = PrimitiveTypes.NUM_POSITIVE
    address = (name, context)
    obj = (context, None)


class NumPosZeroObjectAddress:
    name = "PosZero"
    context = PrimitiveTypes.NUM_POS_ZERO
    address = (name, context)
    obj = (context, None)


class NumPosZeroNegObjectAddress:
    name = "PosZeroNeg"
    context = PrimitiveTypes.NUM_POS_ZERO_NEG
    address = (name, context)
    obj = (context, None)


Num_Add = {
    # - 0
    (NumNegObjectAddress.obj, NumZeroObjectAddress.obj): NumNegObjectAddress.obj,
    # - +
    (NumNegObjectAddress.obj, NumPosObjectAddress.obj): NumPosZeroNegObjectAddress.obj,
    # - (-,0)
    (NumNegObjectAddress.obj, NumNegZeroObjectAddress.obj): NumNegObjectAddress.obj,
    # - (0, +)
    (
        NumNegObjectAddress.obj,
        NumPosZeroObjectAddress.obj,
    ): NumPosZeroNegObjectAddress.obj,
    # 0, (-, 0)
    (
        NumZeroObjectAddress.obj,
        NumNegZeroObjectAddress.obj,
    ): NumNegZeroObjectAddress.obj,
    # 0, +
    (NumZeroObjectAddress.obj, NumPosObjectAddress.obj): NumPosObjectAddress.obj,
    # 0, (0, +)
    (
        NumZeroObjectAddress.obj,
        NumPosZeroObjectAddress.obj,
    ): NumPosZeroNegObjectAddress.obj,
    # (-,0) +
    (
        NumNegZeroObjectAddress.obj,
        NumPosObjectAddress.obj,
    ): NumPosZeroNegObjectAddress.obj,
    # (-, 0) (+, 0)
    (
        NumNegZeroObjectAddress.obj,
        NumPosZeroObjectAddress.obj,
    ): NumPosZeroNegObjectAddress.obj,
    # +, (0, +)
    (NumPosObjectAddress.obj, NumPosZeroObjectAddress.obj): NumPosZeroObjectAddress.obj,
}


class StrEmptyObjectAddress:
    name = "Empty"
    context = PrimitiveTypes.STR_EMPTY
    address = (name, context)
    obj = (context, None)


class StrNonEmptyObjectAddress:
    name = "NonEmpty"
    context = PrimitiveTypes.STR_NON_EMPTY
    address = (name, context)
    obj = (context, None)


class BytesObjectAddress:
    name = "Bytes"
    context = PrimitiveTypes.BYTES
    address = (name, context)
    obj = (context, None)


class UndefObjectAddress:
    name = "Undef"
    context = PrimitiveTypes.UNDEF
    address = (name, context)
    obj = (context, None)


# a mapping used in store
BUILTIN_CLASSES = (
    BoolFalseObjectAddress,
    BoolTrueObjectAddress,
    NoneObjectAddress,
    NumNegObjectAddress,
    NumZeroObjectAddress,
    NumNegZeroObjectAddress,
    NumPosObjectAddress,
    NumPosZeroObjectAddress,
    NumPosZeroNegObjectAddress,
    StrEmptyObjectAddress,
    StrNonEmptyObjectAddress,
    BytesObjectAddress,
    UndefObjectAddress,
)
# a mapping from names to addresses, used in data stack
BUILTIN_CLASS_NAMES = {a.name: a.address for a in BUILTIN_CLASSES}
ZERO_OBJECTS = (
    NumZeroObjectAddress.obj,
    BoolFalseObjectAddress.obj,
    StrEmptyObjectAddress.obj,
    NoneObjectAddress.obj,
)
BOOL_OBJS = {
    BoolFalseObjectAddress.obj: NumZeroObjectAddress.obj,
    BoolTrueObjectAddress.obj: NumPosObjectAddress.obj,
}
NUM_OBJS = {
    NumPosObjectAddress.obj: {4},
    NumZeroObjectAddress.obj: {2},
    NumNegObjectAddress.obj: {1},
    NumNegZeroObjectAddress: {1, 2},
    NumPosZeroObjectAddress: {2, 4},
    NumPosZeroNegObjectAddress: {1, 2, 4},
}
