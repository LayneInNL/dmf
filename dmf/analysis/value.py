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

from collections import defaultdict
from typing import List, Tuple, Dict

import dmf.share
from dmf.analysis.prim import (
    PRIM_BOOL_ID,
    PRIM_INT_ID,
    PRIM_INT,
    PRIM_BOOL,
    PRIM_NONE_ID,
    PRIM_NONE,
    PRIM_STR_ID,
    PRIM_STR,
    PRIM_BYTES_ID,
    PRIM_BYTES,
)

from dmf.log.logger import logger

VALUE_TOP = "VALUE_TOP"


class FuncType:
    def __init__(self, name, module, code):
        self.name = name
        self.qualname = None
        self.module = module
        self.defaults = None
        self.code = code
        self.globals = None
        self.dict: Namespace[str, Value] = Namespace()
        self.closure = None
        self.kwdefaults = None

    def __le__(self, other: FuncType):
        return self.dict <= other.dict

    def __iadd__(self, other: FuncType):
        self.dict += other.dict
        return self

    @property
    def name(self):
        return self._name_

    @name.setter
    def name(self, name):
        self._name_ = name

    @property
    def module(self):
        return self._module_

    @module.setter
    def module(self, module):
        self._module_ = module

    @property
    def code(self):
        return self._code_

    @code.setter
    def code(self, code):
        self._code_ = code

    def setattr(self, attr: str, value: Value):
        var = Var(attr, Namespace_Local)
        self.dict[var] = value

    def getattr(self, name: str) -> Tuple[str, Value]:
        return self.dict.read_scope_and_value_by_name(name)

    # def __repr__(self):
    #     return self._dict_.__repr__()


class MethodType:
    def __init__(self, instance: InsType, func: FuncType, module: str):
        self.name = None
        self.qualname = None
        self.func = func
        self.instance = instance
        self.module = module

    def __le__(self, other: MethodType):
        return self.func <= other.func

    def __iadd__(self, other: MethodType):
        self.func += other.func
        return self

    @property
    def instance(self):
        return self._instance

    @instance.setter
    def instance(self, instance: InsType):
        self._instance: InsType = instance

    @property
    def func(self):
        return self._func

    @func.setter
    def func(self, func: FuncType):
        self._func: FuncType = func

    @property
    def code(self):
        return self.func.code

    @property
    def module(self):
        return self._module

    @module.setter
    def module(self, module: str):
        self._module: str = module


class ClsType:
    def __init__(
        self, name: str, module: str, bases: List, namespace: Namespace[Var, Value]
    ):
        self.name = name
        self.module = module
        self.bases = bases
        self.mro = static_c3(self)
        # the last builtin_object is just a flag, remove it
        self.mro = self.mro[:-1]
        logger.debug("mro for class {}".format(self.mro, self.name))
        self.dict: Namespace[Var, Value] = namespace

    def __repr__(self):
        return self.name

    def __le__(self, other: ClsType):
        return self.dict <= other.dict

    def __iadd__(self, other: ClsType):
        self.dict += other.dict
        return self

    def setattr(self, attr: str, value):
        self.dict[Var(attr, Namespace_Local)] = value

    def getattr(self, name: str) -> Tuple[str, Value]:
        return self.dict.read_scope_and_value_by_name(name)


class InsType:
    def __init__(self, addr, cls_type: ClsType):
        self.addr = addr
        self.cls = cls_type
        self.dict: Namespace[Var, Value] = Namespace()

    def __le__(self, other: InsType):
        return self.dict <= other.dict

    def __iadd__(self, other: InsType):
        self.dict += other.dict
        return self

    def __hash__(self):
        return hash(str(self.addr) + self.cls.name)

    def __eq__(self, other: InsType):
        return self.addr == other.addr and self.cls.name == other.cls.name

    @property
    def addr(self):
        return self._addr

    @addr.setter
    def addr(self, addr):
        self._addr = addr

    def setattr(self, attr: str, value: Value):
        var = Var(attr, Namespace_Local)
        self.dict[var] = value

    def getattr(self, name: str) -> Tuple[str, Value]:
        return self.dict.read_scope_and_value_by_name(name)


class ModuleType:
    def __init__(self, name: str, package: str | None, file: str):
        self.name = name
        self.package = package
        self.file = file
        self.namespace = Namespace()
        self.namespace["__name__"] = name
        self.namespace["__package__"] = package
        self.namespace["__file__"] = file
        self.entry_label, self.exit_label = dmf.share.create_and_update_cfg(self.file)

    def getattr(self, name: str) -> Tuple[str, Value]:
        return self.namespace.read_scope_and_value_by_name(name)


class ListType:
    def __init__(self):
        self.value: Value = Value()

    def __le__(self, other: ListType):
        return self.value <= other.value

    def __iadd__(self, other: ListType):
        self.value += other.value
        return self

    # def __repr__(self):
    #     return self.value.__repr__()


# Either VALUE_TOP or have some values
class Value:
    def __init__(self):
        self.type_dict: Dict | VALUE_TOP = {}

    def __le__(self, other: Value):
        if other.type_dict == VALUE_TOP:
            return True
        if self.type_dict == VALUE_TOP:
            return False

        for k in self.type_dict:
            if k not in other.type_dict:
                return False
            elif not self.type_dict[k] <= other.type_dict[k]:
                return False
        return True

    def __iadd__(self, other: Value):
        if self.type_dict == VALUE_TOP or other.type_dict == VALUE_TOP:
            self.type_dict = VALUE_TOP
            return self

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

    def inject_func_type(self, func_type: FuncType):
        lab = id(func_type)
        self.type_dict[lab] = func_type

    def inject_cls_type(self, cls_type: ClsType):
        lab = id(cls_type)
        self.type_dict[lab] = cls_type

    def inject_ins_type(self, ins_type: InsType):
        lab = id(ins_type)
        self.type_dict[lab] = ins_type

    def inject_method_type(self, method_type: MethodType):
        lab = id(method_type)
        self.type_dict[lab] = method_type

    def inject_module_type(self, module_type: ModuleType):
        lab = id(ModuleType)
        self.type_dict[lab] = module_type

    def extract_cls_type(self):
        res = []
        for _, typ in self.type_dict.items():
            if isinstance(typ, ClsType):
                res.append(typ)
        return res

    def inject_int_type(self):
        lab = PRIM_INT_ID
        self.type_dict[lab] = PRIM_INT

    def inject_float_type(self):
        pass

    def inject_bool_type(self):
        lab = PRIM_BOOL_ID
        self.type_dict[lab] = PRIM_BOOL

    def inject_none_type(self):
        lab = PRIM_NONE_ID
        self.type_dict[lab] = PRIM_NONE

    def inject_str_type(self):
        lab = PRIM_STR_ID
        self.type_dict[lab] = PRIM_STR

    def inject_bytes_type(self):
        lab = PRIM_BYTES_ID
        self.type_dict[lab] = PRIM_BYTES

    def inject_list_type(self, list_type):
        lab = id(list_type)
        self.type_dict[lab] = list_type

    def inject_value(self, value: Value):
        for lab, typ in value.type_dict.items():
            self.type_dict[lab] = typ


class Var:
    def __init__(self, name: str, scope: str = "local"):
        self.name = name
        # scope could be local, nonlocal, global
        self.scope = scope

    def __repr__(self):
        return "({},{})".format(self.name, self.scope)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def scope(self):
        return self._scope

    @scope.setter
    def scope(self, scope):
        self._scope = scope

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other: Var):
        return self.name == other.name


def value_top_builder() -> Value:
    value = Value()
    value.type_dict = VALUE_TOP
    return value


Namespace_Local = "local"
Namespace_Nonlocal = "nonlocal"
Namespace_Global = "global"


# Dict[Var|str, Value|VALUE_TOP]
# Var | str, str represents magic variables, Var represents general variables
# Value | VALUE_TOP, Value represents value, VALUE_TOP represents TOP
class Namespace(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)

    def __missing__(self, key):
        self[key] = value = value_top_builder()
        return value

    def is_magic_attr(self, var: Var | str):
        if isinstance(var, str):
            return True
        else:
            return False

    # we use defaultdict, the default value of an unknown variable is TOP
    # So we have to collect all variables
    def __le__(self, other: Namespace):
        variables = self.keys() | other.keys()
        for var in variables:
            # magic method
            if self.is_magic_attr(var):
                continue
            elif isinstance(var, Var):
                if not self[var] <= other[var]:
                    return False
            else:
                assert False
        return True

    def __iadd__(self, other: Namespace):
        variables = self.keys() | other.keys()
        for var in variables:
            if self.is_magic_attr(var):
                continue
            elif isinstance(var, Var):
                self[var] += other[var]
            else:
                assert False
        return self

    def __contains__(self, name: str):
        # __xxx__ and Var
        for var in self:
            if self.is_magic_attr(var):
                continue
            if name == var.name:
                return True
        return False

    def read_scope_and_value_by_name(self, var_name: str) -> Tuple[str, Value]:
        for var, v_value in self.items():
            if self.is_magic_attr(var):
                continue
            if var_name == var.name:
                return var.scope, v_value
        raise AttributeError(var_name)

    @property
    def module(self):
        return self["__name__"]


Unused_Name = "-1024"
SELF_FLAG = "self"
INIT_FLAG = "19970303"
INIT_FLAG_VALUE = VALUE_TOP
RETURN_FLAG = "__return__"

# builtin_object = ClsType((), Namespace())
# builtin_object = dmf.share.analysis_modules["static_builtins"].namespace["__object__"]


def static_c3(class_object):
    builtin_object = dmf.share.analysis_modules["static_builtins"].namespace[
        "__object__"
    ]
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
