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
from copy import deepcopy
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

builtin_object = object()


def c3(cls_obj):
    mro = static_c3(cls_obj)
    return mro[:-1]


def static_c3(cls_obj):
    if cls_obj is builtin_object:
        return [cls_obj]
    return [cls_obj] + static_merge([static_c3(base) for base in cls_obj.__my_bases__])


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


Namespace_Local = "local"
Namespace_Nonlocal = "nonlocal"
Namespace_Global = "global"


def my_type(obj):
    return obj.__my_class__


def my_hasattr(obj, item):
    try:
        obj.__getattribute__(item)
    except AttributeError:
        return False
    else:
        return True


my_getattr_obj = object()


def my_getattr(obj, name, default=my_getattr_obj):
    get_attribute = find_name_in_mro(my_type(obj), "__getattribute__")
    if get_attribute is None:
        assert False
    try:
        attr_value = get_attribute(obj, name)
    except AttributeError:
        if default is not my_getattr_obj:
            return default
    else:
        if isinstance(attr_value, Instance):
            pass
        return attr_value


def my_setattr(obj, name, value):
    obj.__setattr__(name, value)


def find_name_in_mro(py_type, name):
    mro = py_type.__my_mro__
    for cls in mro:
        if name in cls.__my_dict__:
            val = cls.__my_dict__.read_value(name)
            if isinstance(val, Value):
                assert len(val) == 1
            return val
    return None


def is_nondata_descriptor(value):
    for lab, typ in value:
        if my_hasattr(typ, "__get__"):
            return True
    return False


def is_data_descriptor(value):
    for lab, typ in value:
        if my_hasattr(typ, "__get__"):
            if my_hasattr(typ, "__set__") or my_hasattr(typ, "__delete__"):
                return True
    return False


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
    def __le__(self, other):
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

    def __iadd__(self, other):
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
                if var == name:
                    return True
            if isinstance(var, Var):
                if name == var.name:
                    return True
        return False

    def __deepcopy__(self, memo):
        namespace = Namespace()
        for var, value in self.items():
            copied_var = deepcopy(var, memo)
            # print(value)
            copied_value = deepcopy(value, memo)
            namespace[copied_var] = copied_value

        self_id = id(self)
        if self_id not in memo:
            memo[self_id] = namespace
        return namespace

    def read_scope_and_value_by_name(self, var_name: str) -> Tuple[str, Value]:
        for var, v_value in self.items():
            if is_magic_attr(var):
                continue
            if var_name == var.name:
                return var.scope, v_value
        raise AttributeError(var_name)

    def read_value(self, name):
        for var, v_value in self.items():
            if isinstance(var, str):
                if name == var:
                    return v_value
            if isinstance(var, Var):
                if name == var.name:
                    return v_value
        raise AttributeError(name)


class Class:
    pass


class Object(Class):
    @classmethod
    def __set_cls_attr__(cls):
        cls.__my_bases__ = [builtin_object]
        cls.__my_mro__ = c3(cls)
        namespace = Namespace()
        namespace.update(cls.__dict__)
        cls.__my_dict__ = namespace

    def __init__(self):
        pass

    def __getattribute__(self, name):
        type_of_self = my_type(self)
        cls_value = find_name_in_mro(type_of_self, name)
        if cls_value is not None and is_data_descriptor(cls_value):
            return my_getattr(cls_value, "__get__")
        if name in self.__my_dict__:
            return self.__my_dict__.read_value(name)
        if cls_value is not None and is_nondata_descriptor(cls_value):
            return my_getattr(cls_value, "__get__")
        if cls_value is not None:
            return cls_value

        raise AttributeError(name)

    def __setattr__(self, name, value):
        type_of_self = my_type(self)
        cls_value = find_name_in_mro(type_of_self, name)
        if cls_value is not None and is_data_descriptor(cls_value):
            return my_getattr(cls_value, "__set__")
        if name in self.__my_dict__:
            return self.__my_dict__.read_value(name)


Object.__set_cls_attr__()


class Function(Class):
    @classmethod
    def __set_cls_attr__(cls):
        cls.__my_bases__ = [Object]
        cls.__my_mro__ = c3(cls)
        namespace = Namespace()
        namespace.update(cls.__dict__)
        cls.__my_dict__ = namespace

    def __init__(self, *, uuid, name, module, code):
        self.__my_uuid__ = uuid
        self.__my_name__ = name
        self.__my_module__ = module
        self.__my_code__ = code
        namespace = Namespace()
        namespace.update(self.__dict__)
        self.__my_dict__.update(namespace)

    def __le__(self, other: Function):
        return self.__my_dict__ <= other.__my_dict__

    def __iadd__(self, other: Function):
        self.__my_dict__ += other.__my_dict__
        return self


Function.__set_cls_attr__()


class Method(Class):
    def __init__(self, *, instance, function):
        self.__my_uuid__ = f"{instance.__my_uuid__}-{function.__my_uuid__}"
        self.__my_instance__ = instance
        self.__my_func__ = function

    def __le__(self, other):
        return self.__my_func__ <= other.__my_func__

    def __iadd__(self, other):
        self.__my_func__ += other.__my_func__
        return self


class CustomClass(Class):
    def __init__(self, *, uuid, name, module, bases, namespace):
        self.__my_uuid__ = uuid
        self.__my_name__ = name
        self.__my_module__ = module
        self.__my_bases__ = bases
        self.__my_mro__ = c3(self)
        namespace.update(self.__dict__)
        self.__my_dict__ = namespace

    def __le__(self, other: CustomClass):
        return self.__my_dict__ <= other.__my_dict__

    def __iadd__(self, other: CustomClass):
        self.__my_dict__ += other.__my_dict__
        return self.__my_dict__

    def __deepcopy__(self, memo):
        uuid = deepcopy(self.__my_uuid__, memo)
        name = deepcopy(self.__my_name__, memo)
        module = deepcopy(self.__my_module__, memo)
        bases = deepcopy(self.__my_bases__, memo)
        d = deepcopy(self.__my_dict__, memo)
        custom_class = CustomClass(
            uuid=uuid, name=name, module=module, bases=bases, namespace=d
        )
        return custom_class


class Instance:
    def __init__(self, address, cls):
        self.__my_address__ = address
        self.__my_uuid__ = f"{address}-{cls.__my_uuid__}"
        self.__my_class__ = cls
        namespace = Namespace()
        namespace.update(self.__dict__)
        self.__my_dict__ = namespace

    def __le__(self, other):
        return self.__my_dict__ <= other.__my_dict__

    def __iadd__(self, other):
        self.__my_dict__ += other.__my_dict__
        return self


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
        self.uuid = f"{instance.uuid}-{func.uuid}"
        self.qualname = None
        self.func = func
        self.instance = instance
        self.module = module

    def __le__(self, other: MethodType):
        return self.func <= other.func

    def __iadd__(self, other: MethodType):
        self.func += other.func
        return self


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
        self.uuid = f"{addr}-{cls_type.uuid}"
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
        self.uuid = name
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
        self.uuid = f"{type1.uuid}-{type2.uuid}"
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
        self.internal: Value = Value()
        if elts is not None:
            for lab, elt in elts:
                self.internal.inject_type(elt)

    def __deepcopy__(self, memo):
        copied_uuid = deepcopy(self.uuid, memo)
        copied_internal = deepcopy(self.internal, memo)
        copied = ListIns(copied_uuid, copied_internal)

        self_id = id(self)
        if self_id not in memo:
            memo[self_id] = copied
        return copied

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
        return Namespace_Local, value

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


class _TOP:
    def copy(self):
        return self


TOP = _TOP()


# Either VALUE_TOP or have some values
class Value:
    def __init__(self, typ=None):
        self.type_dict: Dict | TOP = {}
        if typ is not None:
            self.type_dict[typ.uuid] = typ

    def __bool__(self):
        if isinstance(self.type_dict, dict) and self.type_dict:
            return True
        return False

    def __len__(self):
        if self.type_dict == TOP:
            return -1
        return len(self.type_dict)

    def __le__(self, other: Value):
        if other.type_dict == TOP:
            return True
        if self.type_dict == TOP:
            return False

        for k in self.type_dict:
            if k not in other.type_dict:
                return False
            elif not self.type_dict[k] <= other.type_dict[k]:
                return False
        return True

    def __iadd__(self, other: Value):
        if self.type_dict == TOP or other.type_dict == TOP:
            self.type_dict = TOP
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

    def __deepcopy__(self, memo):
        value = Value()
        if self.type_dict == TOP:
            value.type_dict = TOP
        else:
            value.type_dict = deepcopy(self.type_dict, memo)

        self_id = id(self)
        if self_id not in memo:
            memo[self_id] = value
        return value

    def inject_type(self, typ):
        if isinstance(
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
                ClsType,
                ModuleType,
                BuiltinMethodType,
                InsType,
                MethodType,
                SuperIns,
                ListIns,
            ),
        ):
            self.type_dict[typ.uuid] = typ
        elif isinstance(typ, CustomClass):
            self.type_dict[typ.__my_uuid__] = typ
        elif isinstance(typ, Function):
            self.type_dict[typ.__my_uuid__] = typ
        elif isinstance(typ, Instance):
            self.type_dict[typ.__my_uuid__] = typ
        else:
            logger.critical(typ)
            assert False

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
    def __init__(self, name: str, scope: str = Namespace_Local):
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
    value.type_dict = TOP
    return value


Unused_Name = "00_unused_name"
SELF_FLAG = "self"
INIT_FLAG = "00_init_flag"
INIT_FLAG_VALUE = value_top_builder()
RETURN_FLAG = "00__return__flag"


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
        self.singletons[ins][Var(field, Namespace_Local)] = value

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
                assert var_scope == Namespace_Local
            except AttributeError:
                pass
            else:
                new_value = Value()
                for idx, field_typ in var_value:
                    if isinstance(field_typ, FuncType):
                        method_type = MethodType(instance, field_typ, field_typ.module)
                        new_value.inject_type(method_type)
                    else:
                        new_value.type_dict[idx] = field_typ
                return new_value
        return AttributeError(field)

    def copy(self):
        copied = Heap(self)
        return copied


analysis_heap = Heap()
