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
    NUM_NEGATIVE = -10
    NUM_ZERO = -9
    NUM_POSITIVE = -8

    BOOL_FALSE = -7
    BOOL_TRUE = -6

    STR_EMPTY = -5
    STR_NON_EMPTY = -4

    BYTES = -3

    NONE = -2


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


class NumPosObjectAddress:
    name = "Positive"
    context = PrimitiveTypes.NUM_POSITIVE
    address = (name, context)
    obj = (context, None)


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


# a mapping used in store
BUILTIN_CLASSES = (
    BoolFalseObjectAddress,
    BoolTrueObjectAddress,
    NoneObjectAddress,
    NumNegObjectAddress,
    NumZeroObjectAddress,
    NumPosObjectAddress,
    StrEmptyObjectAddress,
    StrNonEmptyObjectAddress,
    BytesObjectAddress,
)
# a mapping from names to addresses, used in data stack
BUILTIN_CLASS_NAMES = {a.name: a.address for a in BUILTIN_CLASSES}
