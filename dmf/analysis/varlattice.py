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

import logging

from .state.space import Obj, Context
from .state.types import PrimitiveTypes
from typing import Set, NewType, Dict, Tuple


class BoolLattice:
    BOT = 1
    BOOL = 2

    mapping = {PrimitiveTypes.BOOL: BOOL}
    format_mapping = {
        BOOL: "Bool",
        BOT: "Bot",
    }

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        logging.debug("value is {}".format(value))
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.BOOL

    def merge(self, other: BoolLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: BoolLattice):
        return self.value <= other.value

    def __repr__(self):
        return "{}".format(self.format_mapping[self.value])


class NoneLattice:
    BOT = 1
    NONE = 2
    mapping = {PrimitiveTypes.NONE: NONE}
    format_mapping = {NONE: "None", BOT: "Bot"}

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.NONE

    def merge(self, other: NoneLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: NoneLattice):
        return self.value <= other.value

    def __repr__(self):
        return "{}".format(self.format_mapping[self.value])


class NumLattice:
    BOT = 1
    NUM = 2
    mapping = {PrimitiveTypes.NUM: NUM}
    format_mapping = {NUM: "Num", BOT: "Bot"}

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.NUM

    def merge(self, other: NumLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: NumLattice):
        return self.value <= other.value

    def __repr__(self):
        return "{}".format(self.format_mapping[self.value])


class StrLattice:
    BOT = 1
    STR = 2
    mapping = {PrimitiveTypes.STR: STR}
    format_mapping = {
        STR: "Str",
        BOT: "Bot",
    }

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.STR

    def merge(self, other: StrLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: StrLattice):
        return self.value <= other.value

    def __repr__(self):
        return self.format_mapping[self.value]


class DictLattice:
    BOT = 1
    DICT = 2
    mapping = {PrimitiveTypes.DICT: DICT}
    format_mapping = {
        DICT: "Dict",
        BOT: "Bot",
    }

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.DICT

    def merge(self, other: DictLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: DictLattice):
        return self.value <= other.value

    def __repr__(self):
        return self.format_mapping[self.value]


class SetLattice:
    BOT = 1
    SET = 2
    mapping = {PrimitiveTypes.SET: SET}
    format_mapping = {
        SET: "Set",
        BOT: "Bot",
    }

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.SET

    def merge(self, other: SetLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: SetLattice):
        return self.value <= other.value

    def __repr__(self):
        return self.format_mapping[self.value]


class ListLattice:
    BOT = 1
    LIST = 2
    mapping = {PrimitiveTypes.LIST: LIST}
    format_mapping = {
        LIST: "List",
        BOT: "Bot",
    }

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.LIST

    def merge(self, other: ListLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: ListLattice):
        return self.value <= other.value

    def __repr__(self):
        return self.format_mapping[self.value]


class TupleLattice:
    BOT = 1
    TUPLE = 2
    mapping = {PrimitiveTypes.TUPLE: TUPLE}
    format_mapping = {
        TUPLE: "Tuple",
        BOT: "Bot",
    }

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.TUPLE

    def merge(self, other: TupleLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: TupleLattice):
        return self.value <= other.value

    def __repr__(self):
        return self.format_mapping[self.value]


class FuncLattice:
    BOT = 1
    FUNC = 2
    mapping = {PrimitiveTypes.FUNC: FUNC}
    format_mapping = {
        FUNC: "Func",
        BOT: "Bot",
    }

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.FUNC

    def merge(self, other: FuncLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: FuncLattice):
        return self.value <= other.value

    def __repr__(self):
        return self.format_mapping[self.value]


class BytesLattice:
    BOT = 1
    BYTES = 2
    mapping = {PrimitiveTypes.BYTES: BYTES}
    format_mapping = {BYTES: "Bytes", BOT: "Bot"}

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.BYTES

    def merge(self, other: BytesLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: BytesLattice):
        return self.value <= other.value

    def __repr__(self):
        return "{}".format(self.format_mapping[self.value])


class UndefLattice:
    BOT = 1
    UNDEF = 2
    mapping = {PrimitiveTypes.UNDEF: UNDEF}
    format_mapping = {UNDEF: "Undef", BOT: "Bot"}

    def __init__(self):
        self.value: int = self.BOT

    def join(self, other: int):
        value: int = self.value + other
        if value in [2]:
            self.value = self.BOT
        elif value in [3, 4]:
            self.value = self.UNDEF

    def merge(self, other: UndefLattice):
        self.join(other.value)

    def from_heap_context_to_lattice(self, heap_context: int):
        self.join(self.mapping[heap_context])

    def is_subset(self, other: UndefLattice):
        return self.value <= other.value

    def __repr__(self):
        return "{}".format(self.format_mapping[self.value])


class VarLattice:
    def __init__(self):
        self.bool_lattice: BoolLattice = BoolLattice()
        self.none_lattice: NoneLattice = NoneLattice()
        self.num_lattice: NumLattice = NumLattice()
        self.str_lattice: StrLattice = StrLattice()
        self.dict_lattice: DictLattice = DictLattice()
        self.set_lattice: SetLattice = SetLattice()
        self.list_lattice: ListLattice = ListLattice()
        self.tuple_lattice: TupleLattice = TupleLattice()
        self.func_lattice: FuncLattice = FuncLattice()
        # self.bytes_lattice: BytesLattice = BytesLattice()
        # self.undef_lattice: UndefLattice = UndefLattice()

    def transform_one(self, obj: Obj):
        heap_context, fields = obj
        if heap_context in [PrimitiveTypes.BOOL]:
            self.bool_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [PrimitiveTypes.NONE]:
            self.none_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [PrimitiveTypes.NUM]:
            self.num_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [PrimitiveTypes.STR]:
            self.str_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [PrimitiveTypes.DICT]:
            self.dict_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [PrimitiveTypes.SET]:
            self.set_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [PrimitiveTypes.LIST]:
            self.list_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [PrimitiveTypes.TUPLE]:
            self.tuple_lattice.from_heap_context_to_lattice(heap_context)
        elif heap_context in [PrimitiveTypes.FUNC]:
            self.func_lattice.from_heap_context_to_lattice(heap_context)
        # elif heap_context in [PrimitiveTypes.BYTES]:
        #     self.bytes_lattice.from_heap_context_to_lattice(heap_context)
        # elif heap_context in [PrimitiveTypes.UNDEF]:
        #     self.undef_lattice.from_heap_context_to_lattice(heap_context)

    def transform(self, objs: Set[Obj]):
        for obj in objs:
            self.transform_one(obj)

    def is_subset(self, other: VarLattice):
        return (
            self.bool_lattice.is_subset(other.bool_lattice)
            and self.none_lattice.is_subset(other.none_lattice)
            and self.num_lattice.is_subset(other.num_lattice)
            and self.str_lattice.is_subset(other.str_lattice)
            and self.dict_lattice.is_subset(other.dict_lattice)
            and self.set_lattice.is_subset(other.set_lattice)
            and self.list_lattice.is_subset(other.list_lattice)
            and self.tuple_lattice.is_subset(other.tuple_lattice)
            and self.func_lattice.is_subset(other.func_lattice)
            # and self.bytes_lattice.is_subset(other.bytes_lattice)
            # and self.undef_lattice.is_subset(other.undef_lattice)
        )

    def merge(self, other: VarLattice):
        self.bool_lattice.merge(other.bool_lattice)
        self.none_lattice.merge(other.none_lattice)
        self.num_lattice.merge(other.num_lattice)
        self.str_lattice.merge(other.str_lattice)
        self.dict_lattice.merge(other.dict_lattice)
        self.set_lattice.merge(other.set_lattice)
        self.list_lattice.merge(other.list_lattice)
        self.tuple_lattice.merge(other.tuple_lattice)
        self.func_lattice.merge(other.func_lattice)
        # self.bytes_lattice.merge(other.bytes_lattice)
        # self.undef_lattice.merge(other.undef_lattice)

    def __repr__(self):
        bool_lattice_str = self.bool_lattice.__repr__()
        none_lattice_str = self.none_lattice.__repr__()
        num_lattice_str = self.num_lattice.__repr__()
        str_lattice_str = self.str_lattice.__repr__()
        dict_lattice_str = self.dict_lattice.__repr__()
        set_lattice_str = self.set_lattice.__repr__()
        list_lattice_str = self.list_lattice.__repr__()
        tuple_lattice_str = self.tuple_lattice.__repr__()
        func_lattice_str = self.func_lattice.__repr__()
        # bytes_lattice_str = self.bytes_lattice.__repr__()
        # undef_lattice_str = self.undef_lattice.__repr__()
        res = (
            "Lattice: Bool x None x Num x Str x Dict x Set x List x Tuple x Func:"
            " {} x {} x {} x {} x {} x {} x {} x {} x {} \n"
        )
        res = res.format(
            bool_lattice_str,
            none_lattice_str,
            num_lattice_str,
            str_lattice_str,
            dict_lattice_str,
            set_lattice_str,
            list_lattice_str,
            tuple_lattice_str,
            func_lattice_str,
            # bytes_lattice_str,
            # undef_lattice_str,
        )
        return res


Lattice = NewType("Lattice", Dict[str, VarLattice])
Context_Lattice = NewType("Context_Lattice", Dict[str, Tuple[Context, VarLattice]])
