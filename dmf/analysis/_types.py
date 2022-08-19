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

# __all__ = ["Namespace_Local", "Namespace_Nonlocal", "Namespace_Global", "Namespace_Helper"]

from __future__ import annotations

from dmf.analysis.exceptions import MROAnyError
from dmf.analysis.special_types import MRO_Any, Bases_Any
from dmf.analysis.value import Value

Namespace_Local = "local"
Namespace_Nonlocal = "nonlocal"
Namespace_Global = "global"
Namespace_Helper = "helper"
POS_ARG_END = "POSITION_FLAG"
INIT_FLAG = "INIT_FLAG"
RETURN_FLAG = "RETURN_FLAG"


class Var:
    def __init__(self, name: str):
        self.name: str = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other: Var):
        return self.name == other.name


class LocalVar(Var):
    def __repr__(self):
        return f"({self.name}, local)"


class NonlocalVar(Var):
    def __repr__(self):
        return f"({self.name}, nonlocal)"


class GlobalVar(Var):
    def __repr__(self):
        return f"({self.name}, global)"


class SpecialVar(Var):
    def __repr__(self):
        return f"({self.name}, special)"


class Namespace(dict):
    def __missing__(self, key):
        self[key] = value = Value.make_any()
        return value

    def __le__(self, other):
        variables = filter(
            lambda elt: not isinstance(elt, SpecialVar),
            self.keys() | other.keys(),
        )
        for var in variables:
            if not self[var] <= other[var]:
                return False
        return True

    def __iadd__(self, other):
        variables = filter(
            lambda elt: not isinstance(elt, SpecialVar),
            self.keys() | other.keys(),
        )
        for var in variables:
            self[var] += other[var]
        return self

    def __contains__(self, name: str):
        for var in self:
            if name == var.name:
                return True
        return False

    def read_var_type(self, name: str) -> Var:
        for var, _ in self.items():
            if name == var.name:
                return var

    def read_value(self, name: str) -> Value:
        for var, val in self.items():
            if name == var.name:
                return val

    def write_local_value(self, name: str, value: Value):
        self[LocalVar(name)] = value

    def write_nonlocal_value(self, name: str, ns: Namespace):
        self[NonlocalVar(name)] = ns

    def write_global_value(self, name: str, ns: Namespace):
        self[GlobalVar(name)] = ns

    def write_special_value(self, name: str, value):
        self[SpecialVar(name)] = value

    def del_local_var(self, name: str):
        del self[LocalVar(name)]


class SpecialAttributes:
    def __init__(self):
        self.tp_uuid = NotImplemented
        self.tp_dict = NotImplemented
        self.tp_class = NotImplemented
        self.tp_mro = NotImplemented
        self.tp_bases = NotImplemented
        # self.tp_name = NotImplemented
        # self.tp_qualname = NotImplemented


class TypeType(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = self

    def __repr__(self):
        return "type"


Type_Type = TypeType()


class TypeObject(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = self, []

    def __repr__(self):
        return "object"


Object_Type = TypeObject()


# if MROAnyError, it means mro can not be fully constructed.
# we only know current class and the rest of mro is Any
def c3(cls_obj):
    try:
        mro = static_c3(cls_obj)
    except MROAnyError:
        return cls_obj, MRO_Any
    else:
        return mro[0], mro[1:]


def static_c3(cls_obj):
    if cls_obj is Object_Type:
        return [cls_obj]
    elif cls_obj.tp_bases is Bases_Any:
        raise MROAnyError
    else:
        return [cls_obj] + static_merge([static_c3(base) for base in cls_obj.tp_bases])


def static_merge(mro_list):
    if not any(mro_list):
        return []
    for candidate, *_ in mro_list:
        if all(candidate not in tail for _, *tail in mro_list):
            return [candidate] + static_merge(
                [
                    tail if head is candidate else [head, *tail]
                    for head, *tail in mro_list
                ]
            )
    else:
        raise TypeError("No legal mro")


Type_Type.tp_bases = [Object_Type]
Type_Type.tp_mro_curr, Type_Type.tp_mro_rest = c3(Type_Type)


class TypeInt(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "int"


Int_Type = TypeInt()


class TypeFloat(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "float"


Float_Type = TypeFloat()


class TypeComplex(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "complex"


Complex_Type = TypeComplex()


class TypeList(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "list"


List_Type = TypeList()


class TypeTuple(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "tuple"


Tuple_Type = TypeTuple()


class TypeRange(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "range"


Range_Type = TypeRange()


class TypeStr(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "str"


Str_Type = TypeStr()


class TypeBytes(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "bytes"


Bytes_Type = TypeBytes()


class TypeByteArray(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "bytearray"


ByteArray_Type = TypeByteArray()


class TypeMemoryView(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "memoryview"


MemoryView_Type = TypeMemoryView()


class TypeSet(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "set"


Set_Type = TypeSet()


class TypeFrozenSet(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "frozenset"


FrozenSet_Type = TypeFrozenSet()


class TypeDict(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "dict"


Dict_Type = TypeDict()


class TypeModule(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "module"


Module_Type = TypeModule()


class TypeFunction(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "function"


Function_Type = TypeFunction()


class TypeMethod(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "method"


Method_Type = TypeMethod()


class TypeNoneType(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "NoneType"


None_Type = TypeNoneType()


class TypeBool(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_bases = [Object_Type]
        self.tp_mro_curr, self.tp_mro_rest = c3(self)

    def __repr__(self):
        return "bool"


Bool_Type = TypeBool()
