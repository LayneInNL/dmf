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

from dmf.log.logger import logger
from collections import defaultdict
from typing import Dict, Any

# None to denote TOP type. it can save memory consumption.
VALUE_TOP = "VALUE_TOP"


def static_c3(class_object):
    if class_object is builtin_object:
        return [class_object]
    return [class_object] + static_merge(
        [static_c3(base) for base in class_object.bases]
    )


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


class Prim:
    pass


class Int(Prim):
    def __init__(self):
        pass

    def __le__(self, other: Int):
        return True

    def __iadd__(self, other: Int):
        return self

    def __repr__(self):
        return "int"

    def setattr(self, key, value):
        logger.warn("set attr to int, ignore")
        assert False

    def getattr(self, key):
        logger.warn("get attr from int, ignore")
        assert False


class Bool(Prim):
    def __init__(self):
        pass

    def __le__(self, other: Bool):
        return True

    def __iadd__(self, other: Bool):
        return self

    def __repr__(self):
        return "bool"

    def setattr(self, key, value):
        logger.warn("set attr to bool, ignore")
        assert False

    def getattr(self, key):
        logger.warn("get attr from bool, ignore")
        assert False


class NoneType(Prim):
    def __init__(self):
        pass

    def __le__(self, other: NoneType):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return "None"

    def setattr(self, key, value):
        logger.warn("set attr to none, ignore")
        assert False

    def getattr(self, key):
        logger.warn("set attr from none, ignore")
        assert False


class Str(Prim):
    def __init__(self):
        pass

    def __le__(self, other: Str):
        return True

    def __iadd__(self, other: Str):
        return self

    def __repr__(self):
        return "None"

    def setattr(self, key, value):
        logger.warn("set attr to none, ignore")
        assert False

    def getattr(self, key):
        logger.warn("set attr from none, ignore")
        assert False


class Bytes(Prim):
    def __init__(self):
        pass

    def __le__(self, other: Bytes):
        return True

    def __iadd__(self, other: Bytes):
        return self

    def __repr__(self):
        return "None"

    def setattr(self, key, value):
        logger.warn("set attr to none, ignore")
        assert False

    def getattr(self, key):
        logger.warn("set attr from none, ignore")
        assert False


PRIM_INT = Int()
PRIM_INT_ID = id(PRIM_INT)
PRIM_BOOL = Bool()
PRIM_BOOL_ID = id(PRIM_BOOL)
PRIM_NONE = NoneType()
PRIM_NONE_ID = id(PRIM_NONE)
PRIM_STR = Str()
PRIM_STR_ID = id(PRIM_STR)
PRIM_BYTES = Bytes()
PRIM_BYTES_ID = id(PRIM_BYTES)


class FuncType:
    def __init__(self, name, entry_lab, exit_lab):
        self._name_ = name
        self._qualname_ = None
        self._module_ = None
        self._defaults_ = None
        self._code_ = (entry_lab, exit_lab)
        self._globals_ = None
        # to model real __dict__ in the function
        self._dict_: ValueDict[str, Value] = ValueDict()
        self._closure_ = None
        self._kwdefaults_ = None

    def __le__(self, other: FuncType):
        return self._dict_ <= other._dict_

    def __iadd__(self, other: FuncType):
        self._dict_ += other._dict_
        return self

    def get_code(self):
        return self._code_

    def setattr(self, key, value):
        self._dict_[key] = value

    def getattr(self, key):
        return self._dict_[key]

    # def __repr__(self):
    #     return self._dict_.__repr__()


class ClsType:
    def __init__(self, namespace: ValueDict[str, Value]):
        self._name_ = None
        self._module_ = None
        self._bases_ = None
        self._dict_: ValueDict[str, Value] = namespace

    # def __repr__(self):
    #     return self._dict_.__repr__()

    def __le__(self, other: ClsType):
        return self._dict_ <= other._dict_

    def __iadd__(self, other: ClsType):
        self._dict_ += other._dict_
        return self

    def setattr(self, key, value):
        self._dict_[key] = value

    # get attributes based on name
    def get_attribute(self, name) -> Value:
        for attr_name in self._dict_:
            if attr_name == name:
                return self._dict_[name]
        raise AttributeError

    def getattr(self, key):
        return self._dict_[key]


class InsType:
    def __init__(self, heap):
        self._self_ = heap
        self._dict_: ValueDict[str, Value] = ValueDict()

    def __le__(self, other: InsType):
        return self._dict_ <= other._dict_

    def __iadd__(self, other: InsType):
        self._dict_ += other._dict_
        return self

    def get_heap(self):
        return self._self_

    def setattr(self, key, value):
        self._dict_[key] = value

    def getattr(self, key):
        return self._dict_[key]


# in order to denote TOP, we need a special value. Since python doesn't support algebraic data types,
# we have to use functions outside class to do operations.


class ModuleType:
    def __init__(self, state):
        self._name_ = None
        self._package_ = None
        self._file_ = None
        self._dict_ = None
        self.state = state

    def read_var_from_module(self, var):
        return self.state.read_var_from_stack(var)

    def __le__(self, other):
        return self.state <= other.state

    def __iadd__(self, other):
        self.state += other.state
        return self


# Either VALUE_TOP or have some values
class Value:
    def __init__(self):
        self.type_dict: Dict[int, FuncType | ClsType | InsType | Prim] = {}

    def __le__(self, other: Value):
        for k in self.type_dict:
            if k not in other.type_dict:
                return False
            else:
                if not self.type_dict[k] <= other.type_dict[k]:
                    return False
        return True

    def __iadd__(self, other: Value):
        for k in other.type_dict:
            if k not in self.type_dict:
                self.type_dict[k] = other.type_dict[k]
            else:
                self.type_dict[k] += other.type_dict[k]
        return self

    def __repr__(self):
        return self.type_dict.__repr__()

    def __iter__(self):
        return iter(self.type_dict.items())

    def inject_heap_type(self, lab, ins_type):
        lab = id(ins_type)
        self.type_dict[lab] = ins_type

    def inject_func_type(self, lab, func_type: FuncType):
        lab = id(func_type)
        self.type_dict[lab] = func_type

    def inject_cls_type(self, lab, cls_type: ClsType):
        lab = id(cls_type)
        self.type_dict[lab] = cls_type

    def inject_int_type(self):
        lab = id(PRIM_INT)
        self.type_dict[lab] = PRIM_INT

    def inject_bool_type(self):
        lab = id(PRIM_BOOL)
        self.type_dict[lab] = PRIM_BOOL

    def inject_none_type(self):
        lab = id(PRIM_NONE)
        self.type_dict[lab] = PRIM_NONE

    def inject_str_type(self):
        lab = id(PRIM_STR)
        self.type_dict[lab] = PRIM_STR

    def inject_bytes_type(self):
        self.type_dict[-5] = PRIM_BYTES


# Dict[str, AbstractValue|VALUE_TOP]
class ValueDict(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)

    def __missing__(self, key):
        self[key] = value = VALUE_TOP
        return value

    def issubset(self, this: Value | VALUE_TOP, other: Value | VALUE_TOP):
        if other == VALUE_TOP:
            return True
        if this == VALUE_TOP:
            return False
        return this <= other

    def union(self, this: Value | VALUE_TOP, other: Value | VALUE_TOP):
        if this == VALUE_TOP or other == VALUE_TOP:
            return VALUE_TOP
        this += other
        return this

    # we use defaultdict, the default value of an unknown variable is TOP
    # So we have to collect all variables
    def __le__(self, other: ValueDict):
        variables = self.keys() | other.keys()
        for var in variables:
            if var.startswith("__") and var.endswith("__"):
                continue
            if not self.issubset(self[var], other[var]):
                return False
        return True

    def __iadd__(self, other: ValueDict):
        variables = self.keys() | other.keys()
        for var in variables:
            if var.startswith("__") and var.endswith("__"):
                continue
            self[var] = self.union(self[var], other[var])
        return self


SELF_FLAG = "self"
INIT_FLAG = "19970303"
INIT_FLAG_VALUE = Value()
RETURN_FLAG = "__return__"
