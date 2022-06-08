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
from typing import List, Tuple, Dict, DefaultDict

import dmf.share
from dmf.analysis.prim import (
    Int,
    Bool,
    NoneType,
    Str,
    Bytes,
    SuperType,
    ListType,
    DictType,
    SetType,
    TupleType,
)
from dmf.log.logger import logger


class FuncType:
    def __init__(self, label, name, module, code):
        self.uuid = label
        self.name = name
        self.qualname = None
        self.module = module
        self.defaults = None
        self.code = code
        self.globals = None
        self.dict: Namespace[Var, Value] = Namespace()
        self.closure = None
        self.kwdefaults = None

    def __le__(self, other: FuncType):
        return self.dict <= other.dict

    def __iadd__(self, other: FuncType):
        self.dict += other.dict
        return self

    def __repr__(self):
        return self.dict.__repr__()

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
        if attr in self.dict:
            _, attr_value = self.dict.read_scope_and_value_by_name(attr)
            attr_value.inject_value(value)
        else:
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
        self,
        label: int,
        name: str,
        module: str,
        bases: List,
        namespace: Namespace[Var, Value],
    ):
        self.uuid = label
        self.name = name
        self.module = module
        self.bases = bases
        self.mro = static_c3(self)
        # the last builtin_object is just a flag, remove it
        self.mro = self.mro[:-1]
        logger.critical("mro for class {}".format(self.mro, self.name))
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
        analysis_heap.write_ins_to_heap(self)

    def __le__(self, other: InsType):
        return self.dict <= other.dict

    def __iadd__(self, other: InsType):
        self.dict += other.dict
        return self

    def __hash__(self):
        return hash(str(self.addr) + str(self.cls.uuid))

    def __eq__(self, other: InsType):
        return self.addr == other.addr and self.cls.uuid == other.cls.uuid

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


class SuperIns:
    def __init__(self, type1: ClsType, type2: InsType):
        instance_mro = type2.cls.mro
        idx = instance_mro.index(type1) + 1
        self.proxy_location = idx
        self.proxy_class = instance_mro[idx]
        self.proxy_instance = type2
        self.uuid = "{}-{}".format(type1.uuid, type2.addr)

    def getattr(self, field: str):
        return analysis_heap.read_field_from_class(
            self.proxy_instance, field, self.proxy_location
        )

    def __le__(self, other: SuperIns):
        return True

    def __iadd__(self, other: SuperIns):
        return self


class BuiltinMethodType:
    def __init__(self, uuid, func):
        self.uuid = uuid
        self.func = func

    def __le__(self, other: BuiltinMethodType):
        return True

    def __iadd__(self, other: BuiltinMethodType):
        return self


class ListIns:
    def __init__(self, uuid, elts: Value = None):
        self.uuid = uuid
        self.internal = Value()
        if elts is not None:
            for lab, elt in elts:
                self.internal.inject_type(elt)

    def __le__(self, other: ListIns):
        return self.internal <= other.internal

    def __iadd__(self, other: ListIns):
        self.internal += other.internal

    def __repr__(self):
        return self.internal.__repr__()

    def getattr(self, attr: str):
        func = getattr(self, attr)
        builtin_method_uuid = f"{self.uuid}-{attr}"
        builtin_method = BuiltinMethodType(builtin_method_uuid, func)
        value = Value(builtin_method)
        return "local", value

    def append(self, x):
        self.internal += x
        return NoneType()

    def extend(self, iterable):
        self.internal += iterable

    def insert(self, i, x):
        self.append(x)

    def remove(self, x):
        assert False

    def pop(self, i=None):
        assert False

    def clear(self):
        self.internal = Value()

    def index(self, x, start=None, end=None):
        return Int()

    def count(self, x):
        return Int()

    def sort(self, key=None, reverse=False):
        pass

    def reverse(self):
        pass

    def copy(self):
        assert False


class TOP:
    def copy(self):
        return self


VALUE_TOP = TOP()


# Either VALUE_TOP or have some values
class Value:
    def __init__(self, typ=None):
        self.type_dict: Dict | VALUE_TOP = {}
        if typ is not None:
            self.type_dict[typ.uuid] = typ

    def __bool__(self):
        if isinstance(self.type_dict, dict) and self.type_dict:
            return True
        return False

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

    def copy(self):
        value = Value()
        value.type_dict = self.type_dict.copy()
        return value

    def inject_type(self, typ):
        if isinstance(typ, ClsType):
            self.inject_cls_type(typ)
        elif isinstance(typ, InsType):
            self.inject_ins_type(typ)
        elif isinstance(typ, MethodType):
            self.inject_method_type(typ)
        elif isinstance(typ, ModuleType):
            self.inject_module_type(typ)
        elif isinstance(typ, SuperIns):
            self.inject_super_ins(typ)
        elif isinstance(typ, ListIns):
            self.type_dict[typ.uuid] = typ
        elif isinstance(typ, BuiltinMethodType):
            self.type_dict[typ.uuid] = typ
        elif isinstance(
            typ,
            (
                Int,
                Bool,
                NoneType,
                Str,
                Bytes,
                ListType,
                TupleType,
                SetType,
                DictType,
                SuperType,
                FuncType,
            ),
        ):
            self.type_dict[typ.uuid] = typ
        else:
            assert False

    def inject_super_ins(self, super_type: SuperIns):
        lab = super_type.uuid
        self.type_dict[lab] = super_type

    def inject_cls_type(self, cls_type: ClsType):
        lab = cls_type.uuid
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

    def inject_value(self, value: Value):
        for lab, typ in value.type_dict.items():
            if lab not in self.type_dict:
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


def is_magic_attr(var: Var | str):
    if isinstance(var, str):
        return True
    else:
        return False


# Namespace[Var|str, Value]
class Namespace(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)

    def __missing__(self, key):
        self[key] = value = value_top_builder()
        return value

    # we use defaultdict, the default value of an unknown variable is TOP
    # So we have to collect all variables
    def __le__(self, other: Namespace):
        variables = self.keys() | other.keys()
        for var in variables:
            # magic method
            if is_magic_attr(var):
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
            if is_magic_attr(var):
                continue
            elif isinstance(var, Var):
                self[var] += other[var]
            else:
                assert False
        return self

    def __contains__(self, name: str):
        # __xxx__ and Var
        for var in self:
            if is_magic_attr(var):
                continue
            if name == var.name:
                return True
        return False

    def copy(self):
        namespace = Namespace()
        for var, var_value in self.items():
            if is_magic_attr(var):
                namespace[var] = var_value
            elif isinstance(var, Var):
                namespace[var] = var_value.copy()
        return namespace

    def read_scope_and_value_by_name(self, var_name: str) -> Tuple[str, Value]:
        for var, v_value in self.items():
            if is_magic_attr(var):
                continue
            if var_name == var.name:
                return var.scope, v_value
        raise AttributeError(var_name)

    @property
    def module(self):
        return self["__name__"]


Unused_Name = "00_unused_name"
SELF_FLAG = "self"
INIT_FLAG = "00_init_flag"
INIT_FLAG_VALUE = value_top_builder()
RETURN_FLAG = "00__return__flag"

# builtin_object = ClsType((), Namespace())
# builtin_object = dmf.share.analysis_modules["static_builtins"].namespace["__object__"]

builtin_object = object()


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


class Heap:
    def __init__(self, heap: Heap = None):
        self.singletons: DefaultDict[InsType, Namespace[Var, Value]] = defaultdict(
            Namespace
        )
        if heap is not None:
            self.singletons.copy()

    def __le__(self, other: Heap):
        for ins in self.singletons:
            if ins not in other.singletons:
                return False
            else:
                self_dict = self.singletons[ins]
                other_dict = other.singletons[ins]
                for field in self_dict:
                    if field not in other_dict:
                        return False
                    elif not self_dict[field] <= other_dict[field]:
                        return False
        return True

    def __iadd__(self, other: Heap):
        for ins in other.singletons:
            if ins not in self.singletons:
                self.singletons[ins] = other.singletons[ins]
            else:
                self_dict = self.singletons[ins]
                other_dict = other.singletons[ins]
                for field in other_dict:
                    if field not in self.singletons:
                        self_dict[field] = other_dict[field]
                    else:
                        self_dict[field] += other_dict[field]
        return self

    def __repr__(self):
        return "singleton: {}".format(self.singletons)

    def write_ins_to_heap(self, ins: InsType):
        if ins in self.singletons:
            pass
        else:
            self.singletons[ins] = Namespace()

    def write_field_to_heap(self, ins: InsType, field: str, value: Value):
        self.singletons[ins][Var(field, "local")] = value

    # function
    def read_field_from_instance(self, ins: InsType, field: str):
        if field in self.singletons[ins]:
            var_scope, var_value = self.singletons[ins].read_scope_and_value_by_name(
                field
            )
            return var_value
        else:
            return self.read_field_from_class(ins, field)

    def read_field_from_class(self, instance: InsType, field: str, index=0):
        cls_type: ClsType = instance.cls
        cls_mro: List[ClsType] = cls_type.mro
        considered_cls_mro = cls_mro[index:]
        for typ in considered_cls_mro:
            try:
                var_scope, var_value = typ.getattr(field)
                assert var_scope == "local"
            except AttributeError:
                pass
            else:
                new_value = Value()
                for idx, field_typ in var_value:
                    if isinstance(field_typ, FuncType):
                        method_type = MethodType(instance, field_typ, field_typ.module)
                        new_value.inject_method_type(method_type)
                    else:
                        new_value.type_dict[idx] = field_typ
                return new_value
        return AttributeError(field)

    def copy(self):
        copied = Heap(self)
        return copied


analysis_heap = Heap()
