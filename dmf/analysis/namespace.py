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
from typing import DefaultDict

import dmf.share
from dmf.analysis.c3 import builtin_object, c3
from dmf.analysis.value import Value
from dmf.analysis.variables import (
    DunderVar,
    LocalVar,
    Var,
    NonlocalVar,
    GlobalVar,
    Namespace_Local,
)
from dmf.log.logger import logger


def _func():
    pass


function = type(_func)


def my_type(obj):
    return obj.__my_class__


def my_hasattr(obj, name):
    try:
        _ = my_getattr(obj, name)
    except AttributeError:
        return False
    else:
        return True


my_getattr_obj = object()


def my_getattr(obj, name: str, default=my_getattr_obj) -> Value:

    get_attribute = dunder_lookup(my_type(obj), "__getattribute__")

    attr_value = Value()
    try:
        res = get_attribute(obj, name)
    except AttributeError:
        if default is not my_getattr_obj:
            return default
        raise
    else:
        attr_value.inject_value(res)
        return attr_value


def my_setattr(obj, name, value):
    set_attr = dunder_lookup(my_type(obj), "__setattr__")
    res = set_attr(obj, name, value)
    if res is not None:
        raise NotImplementedError


def dunder_lookup(typ, name: str):

    mro = typ.__my_mro__

    for cls in mro:
        if name in cls.__my_dict__:
            value = cls.__my_dict__.read_value(name)
            assert isinstance(value, Value) and len(value) == 1
            for typ in value:
                return typ
    raise AttributeError


# Namespace[Var|str, Value]
class Namespace(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)

    def __missing__(self, key):
        self[key] = value = Value(top=True)
        return value

    # we use defaultdict, the default value of an unknown variable is TOP
    # So we have to collect all variables
    def __le__(self, other):
        variables = filter(
            lambda elt: not isinstance(elt, DunderVar), self.keys() | other.keys()
        )

        for var in variables:
            if not self[var] <= other[var]:
                return False
        return True

    def __iadd__(self, other):
        variables = filter(
            lambda elt: not isinstance(elt, DunderVar), self.keys() | other.keys()
        )
        for var in variables:
            self[var] += other[var]
        return self

    def __contains__(self, name: str):
        # __xxx__ and Var
        for var in self:
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

        memo[id(self)] = namespace
        return namespace

    def read_var(self, name: str) -> Var:
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

    def write_dunder_value(self, name: str, value):
        self[DunderVar(name)] = value


class TypeClass:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)

            def __getattribute__(cls, name):
                mro = cls.__my_mro__

                for c in mro:
                    if name in c.__my_dict__:
                        value: Value = c.__my_dict__.read_value(name)
                        return value
                raise AttributeError(name)

            def __setattr__(cls, name, value):
                type_of_self = my_type(cls)
                cls_var: Value = my_getattr(type_of_self, name, None)
                if cls_var is not None:
                    data_desc = Value()
                    assert len(cls_var) == 1, cls_var
                    for typ in cls_var:
                        if my_hasattr(typ, "__set__"):
                            desc_get = my_getattr(typ, "__set__")
                            data_desc.inject_value(desc_get)
                    return data_desc

                if hasattr(cls, "__my_dict__"):
                    cls.__my_dict__.write_local_value(name, value)
                    return None
                else:
                    raise NotImplementedError

            self = cls.instance
            self.__my_uuid__ = id(self)
            self.__my_dict__ = Namespace()
            self.__my_bases__ = [builtin_object]
            self.__my_mro__ = c3(self)
            self.__my_class__ = self
            func = SpecialFunctionObject(func=__getattribute__)
            value = Value()
            value.inject_type(func)
            self.__my_dict__.write_local_value(__getattribute__.__name__, value)
            func = SpecialFunctionObject(func=__setattr__)
            value = Value()
            value.inject_type(func)
            self.__my_dict__.write_local_value(__setattr__.__name__, value)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self


class ObjectClass:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)

            def __init__(self):
                return self

            def __getattribute__(self, name):
                type_of_self = my_type(self)
                cls_var: Value = my_getattr(type_of_self, name, None)
                # if cls_var is not None:
                #     data_desc = Value()
                #     assert len(cls_var) == 1, cls_var
                #     for typ in cls_var:
                #         if my_hasattr(typ, "__get__") and (
                #             my_hasattr(typ, "__set__") or my_hasattr(typ, "__delete__")
                #         ):
                #             desc_get = my_getattr(typ, "__get__")
                #             data_desc.inject_value(desc_get)
                #     return data_desc

                if hasattr(self, "__my_dict__") and name in self.__my_dict__:
                    return self.__my_dict__.read_value(name)

                if cls_var is not None:
                    non_data_desc = Value()
                    assert len(cls_var) == 1, cls_var
                    for typ in cls_var:
                        if isinstance(typ, FunctionObject):
                            non_data_desc.inject_type(
                                MethodObject(instance=self, function=typ)
                            )
                        # if my_hasattr(typ, "__get__"):
                        #     desc_get = my_getattr(typ, "__get__")
                        #     for _, getter in desc_get:
                        #         if isinstance(getter, SpecialFunctionObject):
                        #             res = getter(typ, self)
                        #         else:
                        #             res = getter
                        #         non_data_desc.inject_value(res)
                    return non_data_desc

                if cls_var is not None:
                    return cls_var

                raise AttributeError(name)

            def __setattr__(self, name, value):
                type_of_self = my_type(self)
                cls_var: Value = my_getattr(type_of_self, name, None)
                if cls_var is not None:
                    data_desc = Value()
                    assert len(cls_var) == 1, cls_var
                    for _, typ in cls_var:
                        if my_hasattr(typ, "__set__"):
                            desc_get = my_getattr(typ, "__set__")
                            data_desc.inject_value(desc_get)
                    return data_desc

                if isinstance(self, Instance):
                    analysis_heap.write_field_to_heap(self, name, value)
                else:
                    self.__my_dict__.write_local_value(name, value)
                return None

            self = cls.instance
            self.__my_uuid__ = id(self)
            self.__my_dict__ = Namespace()
            self.__my_bases__ = [builtin_object]
            self.__my_mro__ = c3(self)
            self.__my_class__ = my_typ
            value = Value()
            func = SpecialFunctionObject(func=__init__)
            value.inject_type(func)
            self.__my_dict__.write_local_value(__init__.__name__, value)
            value = Value()
            func = SpecialFunctionObject(func=__getattribute__)
            value.inject_type(func)
            self.__my_dict__.write_local_value(__getattribute__.__name__, value)
            value = Value()
            func = SpecialFunctionObject(func=__setattr__)
            value.inject_type(func)
            self.__my_dict__.write_local_value(__setattr__.__name__, value)
            value = Value()
            value.inject_type(constructor)
            self.__my_dict__.write_local_value("__new__", value)
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self


class FunctionClass:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
            self = cls.instance
            self.__my_uuid__ = id(self)
            self.__my_bases__ = [my_object]
            self.__my_mro__ = c3(self)
            self.__my_class__ = my_typ
            self.__my_dict__ = Namespace()
        return cls.instance

    def __le__(self, other: FunctionClass):
        return True

    def __iadd__(self, other: FunctionClass):
        return self


class FunctionObject:
    def __init__(self, *, uuid, name, module, code):
        self.__my_uuid__ = uuid
        self.__my_name__ = name
        self.__my_module__ = module
        self.__my_code__ = code
        self.__my_dict__ = Namespace()
        self.__my_class__ = my_function

    def __le__(self, other):
        return self.__my_dict__ <= other.__my_dict__

    def __iadd__(self, other):
        self.__my_dict__ += other.__my_dict__
        return self


class SpecialFunctionObject:
    def __init__(self, *, func):
        self.__my_uuid__ = id(func)
        self.__my_name__ = func.__name__
        self.__my_code__ = func
        self.__my_dict__ = Namespace()

    def __le__(self, other):
        return self.__my_dict__ <= other.__my_dict__

    def __iadd__(self, other):
        self.__my_dict__ += other.__my_dict__
        return self

    def __call__(self, *args, **kwargs):
        return self.__my_code__(*args, **kwargs)

    def __repr__(self):
        return self.__my_name__


class MethodObject:
    def __init__(self, *, instance: Instance, function: FunctionObject):
        self.__my_uuid__ = f"{instance.__my_uuid__}-{function.__my_uuid__}"
        self.__my_instance__ = instance
        self.__my_func__ = function
        self.__my_module__ = function.__my_module__

    def __le__(self, other):
        return self.__my_func__ <= other.__my_func__

    def __iadd__(self, other):
        self.__my_func__ += other.__my_func__
        return self


class SpecialMethodObject:
    def __init__(self, *, instance: Instance, function: SpecialFunctionObject):
        self.__my_uuid__ = f"{instance.__my_uuid__}-{id(function)}"
        self.__my_name__ = function.__my_name__
        self.__my_instance__ = instance
        self.__my_func__ = function

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __call__(self, *args, **kwargs):
        return self.__my_func__(self.__my_instance__, *args, **kwargs)


class CustomClass:
    def __init__(self, *, uuid, name, module, bases, namespace):
        self.__my_uuid__ = uuid
        self.__my_name__ = name
        self.__my_module__ = module
        self.__my_bases__ = bases
        self.__my_mro__ = c3(self)
        self.__my_dict__ = namespace
        self.__my_class__ = my_typ

    def __le__(self, other: CustomClass):
        return self.__my_dict__ <= other.__my_dict__

    def __iadd__(self, other: CustomClass):
        self.__my_dict__ += other.__my_dict__
        return self

    def __deepcopy__(self, memo):
        uuid = deepcopy(self.__my_uuid__, memo)
        name = deepcopy(self.__my_name__, memo)
        module = deepcopy(self.__my_module__, memo)
        bases = deepcopy(self.__my_bases__, memo)
        d = deepcopy(self.__my_dict__, memo)
        custom_class = CustomClass(
            uuid=uuid, name=name, module=module, bases=bases, namespace=d
        )
        memo[id(self)] = custom_class
        return custom_class


class Constructor:
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = id(cls.instance)
        return cls.instance

    def __call__(self, address, cls):
        return Instance(address=address, cls=cls)

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class Instance:
    def __init__(self, *, address, cls):
        self.__my_address__ = address
        self.__my_uuid__ = f"{address}-{cls.__my_uuid__}"
        self.__my_class__ = cls
        analysis_heap.write_ins_to_heap(self)

    def __le__(self, other: Instance):
        return analysis_heap.singletons[self] <= analysis_heap.singletons[other]

    def __iadd__(self, other: Instance):
        analysis_heap.singletons[self] += analysis_heap.singletons[other]
        return self

    def __hash__(self):
        return hash(self.__my_uuid__)

    def __eq__(self, other):
        return self.__my_uuid__ == other.__my_uuid__


class ModuleType:
    def __init__(self, name: str, package: str | None, file: str):
        self.name = name
        self.uuid = name
        self.package = package
        self.file = file
        self.namespace = Namespace()
        self.namespace.write_dunder_value("__name__", name)
        self.namespace.write_dunder_value("__package__", package)
        self.namespace.write_dunder_value("__file__", file)
        self.entry_label, self.exit_label = dmf.share.create_and_update_cfg(self.file)

    def getattr(self, name: str) -> Value:
        return self.namespace.read_value(name)


# class SuperIns:
#     def __init__(self, type1, type2):
#         self.uuid = f"{type1.uuid}-{type2.uuid}"
#         instance_mro = type2.cls.mro
#         idx = instance_mro.index(type1) + 1
#         self.proxy_location = idx
#         self.proxy_class = instance_mro[idx]
#         self.proxy_instance = type2
#         self.uuid = "{}-{}".format(type1.uuid, type2.addr)
#
#     def getattr(self, field: str):
#         return analysis_heap.read_field_from_class(
#             self.proxy_instance, field, self.proxy_location
#         )
#
#     def __le__(self, other: SuperIns):
#         return True
#
#     def __iadd__(self, other: SuperIns):
#         return self


class Heap:
    def __init__(self, heap: Heap = None):
        self.singletons: DefaultDict[Instance, Namespace[Var, Value]] = defaultdict(
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

    def write_ins_to_heap(self, instance: Instance):
        if instance in self.singletons:
            logger.critical("Have same name")
        else:
            self.singletons[instance] = Namespace()

    def write_field_to_heap(self, instance: Instance, field: str, value: Value):
        self.singletons[instance][LocalVar(field)] = value

    def copy(self):
        copied = Heap(self)
        return copied


constructor = Constructor()
analysis_heap = Heap()
my_typ = TypeClass()
my_object = ObjectClass()
my_function = FunctionClass()
mock_value = Value()
