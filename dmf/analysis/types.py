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

import ast
import types
from copy import copy
from typing import Dict

import dmf.share
from dmf.analysis.c3 import c3
from dmf.analysis.namespace import Namespace
from dmf.analysis.prim import NoneType, Int, Bool
from dmf.analysis.typeshed_types import TypeshedClass, TypeshedFunction
from dmf.analysis.value import Value, create_value_with_type
from dmf.analysis.variables import (
    LocalVar,
    Var,
)


def Type(obj):
    return obj.nl__class__


def Hasattr(obj, name):
    try:
        _ = Getattr(obj, name)
    except AttributeError:
        return False
    else:
        return True


my_getattr_obj = object()


def Getattr(obj, name: str, default=my_getattr_obj) -> Value:

    get_attribute = dunder_lookup(Type(obj), "__getattribute__")

    attr_value = Value()
    try:
        res = get_attribute(obj, name)
    except AttributeError:
        if default is not my_getattr_obj:
            return default
        raise
    else:
        attr_value.inject(res)
        return attr_value


def Setattr(obj, name, value):
    set_attr = dunder_lookup(Type(obj), "__setattr__")
    res = set_attr(obj, name, value)
    return res


def _PyType_Lookup(_type, _name):
    if isinstance(_type, TypeshedClass):
        if _name in _type.child_nodes:
            nameinfo = _type.child_nodes[_name]
            if isinstance(nameinfo.ast, (ast.FunctionDef, ast.AnnAssign, ast.ClassDef)):
                qualified_name = _type.nl__uuid__ + (nameinfo.name,)
                res = TypeshedFunction(qualified_name, nameinfo)
            else:
                raise NotImplementedError
    elif isinstance(_type, CustomClass):
        mro = _type.nl__mro__
        for cls in mro:
            if _name in cls.nl__dict__:
                var = cls.nl__dict__.read_var_type(_name)
                assert isinstance(var, LocalVar)
                value: Value = cls.nl__dict__.read_value(_name)
                return value
        return None


def dunder_lookup(typ, name: str):

    mro = typ.nl__mro__

    for cls in mro:
        if name in cls.nl__dict__:
            value = cls.nl__dict__.read_value(name)
            assert isinstance(value, Value) and len(value) == 1
            for typ in value:
                return typ
    raise AttributeError


class TypeMeta(type):
    def __init__(cls, name, bases, dict):
        super().__init__(name, bases, dict)
        cls.nl__dict__ = Namespace()
        cls.nl__uuid__ = id(cls)

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeClass(metaclass=TypeMeta):
    pass


def _setup_TypeClass():
    def nl__getattribute__(type, name):
        metatype = Type(type)

        meta_attribute = _PyType_Lookup(metatype, name)
        if meta_attribute is not None:
            assert False, meta_attribute

        attribute = _PyType_Lookup(type, name)
        cls_vars = attribute
        if cls_vars is not None:
            descr_get = Value()
            for cls_var in cls_vars:
                if isinstance(cls_var, FunctionClass):
                    descr_get.inject(cls_var)
                elif isinstance(cls_var, SpecialFunctionClass):
                    descr_get.inject(cls_var)
                else:
                    cls_var_type = Type(cls_var)
                    cls_var_type_getters = _PyType_Lookup(cls_var_type, "nl__get__")
                    if cls_var_type_getters is not None:
                        for getter in cls_var_type_getters:
                            if isinstance(getter, FunctionClass):
                                method_getter = MethodClass(
                                    instance=cls_var,
                                    function=getter,
                                    descr_instance=NoneType(),
                                    descr_owner=type,
                                )
                                descr_get.inject(method_getter)
                            else:
                                assert False, getter
            if len(descr_get) > 0:
                return descr_get

        assert False, type
        raise AttributeError(name)

    def nl__setattr__(self, name, value):
        cls_vars: Value = _PyType_Lookup(self, name)
        descr_setters = Value()
        if cls_vars is not None:
            for cls_var in cls_vars:
                cls_var_type = Type(cls_var)
                setters = _PyType_Lookup(cls_var_type, "nl__set__")
                for setter in setters:
                    if isinstance(setter, FunctionClass):
                        descr_setters.inject(
                            MethodClass(
                                instance=cls_var,
                                function=setter,
                                descr_instance=self,
                                descr_value=value,
                            )
                        )
                        descr_setters.inject(setters)
                    else:
                        assert False, setter
        if value is None:
            if isinstance(self, Instance):
                if self not in analysis_heap:
                    analysis_heap.write_instance_dict(self)
                instance_dict = analysis_heap.read_instance_dict(self)
                instance_dict.del_local_var(name)
            elif hasattr(self, "nl__dict__"):
                self.nl__dict__.del_load_var(name)
        else:
            if isinstance(self, Instance):
                if self not in analysis_heap:
                    analysis_heap.write_instance_dict(self)
                instance_dict = analysis_heap.read_instance_dict(self)
                instance_dict.write_local_value(name, value)
            elif hasattr(self, "nl__dict__"):
                self.nl__dict__.write_local_value(name, value)
        return descr_setters

    cls_dict = Namespace()
    local_functions = filter(
        lambda value: isinstance(value, types.FunctionType),
        locals().values(),
    )
    for function in local_functions:
        cls_dict.write_local_value(
            function.__name__,
            create_value_with_type(SpecialFunctionClass(function=function)),
        )
    return cls_dict


class ObjectClass(metaclass=TypeMeta):
    pass


def _setup_ObjectClass():
    def nl__init__(self):
        return self

    def nl__getattribute__(self, name):
        # type_of_self = type(self)
        self_type = Type(self)
        # get class variables
        cls_vars: Value = _PyType_Lookup(self_type, name)

        if cls_vars is not None:
            data_descr_getters = Value()
            for cls_var in cls_vars:
                cls_var_type = Type(cls_var)
                descr_getters = _PyType_Lookup(cls_var_type, "nl__get__")
                if descr_getters is not None:
                    descr_setters = _PyType_Lookup(cls_var_type, "nl__set__")
                    if descr_setters is not None:
                        for getter in descr_getters:
                            if isinstance(getter, FunctionClass):
                                method_getter = MethodClass(
                                    instance=cls_var,
                                    function=getter,
                                    descr_instance=self,
                                    descr_owner=self_type,
                                )
                                data_descr_getters.inject(method_getter)
                            else:
                                assert False, getter
            if len(data_descr_getters) > 0:
                return data_descr_getters

        if isinstance(self, Instance) and self in analysis_heap:
            instance_dict = analysis_heap.read_instance_dict(self)
            if name in instance_dict:
                return instance_dict.read_value(name)
        elif hasattr(self, "nl__dict__") and name in self.nl__dict__:
            return self.nl__dict__.read_value(name)

        if cls_vars is not None:
            nondata_descr_getters = Value()
            for cls_var in cls_vars:
                if isinstance(cls_var, FunctionClass):
                    nondata_descr_getters.inject(
                        MethodClass(instance=self, function=cls_var)
                    )
                elif isinstance(cls_var, SpecialFunctionClass):
                    nondata_descr_getters.inject(
                        SpecialMethodClass(instance=self, function=cls_var)
                    )
                else:
                    cls_var_type = Type(cls_var)
                    descr_getters = _PyType_Lookup(cls_var_type, "nl__get__")
                    if descr_getters is not None:
                        for getter in descr_getters:
                            if isinstance(getter, FunctionClass):
                                method_getter = MethodClass(
                                    instance=cls_var,
                                    function=getter,
                                    descr_instance=self,
                                    descr_owner=self_type,
                                )
                                nondata_descr_getters.inject(method_getter)
                            else:
                                assert False, getter
            if len(nondata_descr_getters) > 0:
                return nondata_descr_getters
        if cls_vars is not None:
            return cls_vars

        raise AttributeError(name)

    def nl__setattr__(self, name, value):
        self_type = Type(self)
        cls_vars: Value = _PyType_Lookup(self_type, name)

        descr_setters = Value()
        if cls_vars is not None:
            for cls_var in cls_vars:
                cls_var_type = Type(cls_var)
                setters = _PyType_Lookup(cls_var_type, "nl__set__")
                for setter in setters:
                    if isinstance(setter, FunctionClass):
                        descr_setters.inject(
                            MethodClass(
                                instance=cls_var,
                                function=setter,
                                descr_instance=self,
                                descr_value=value,
                            )
                        )
                        descr_setters.inject(setters)
                    else:
                        assert False, setter
        if value is None:
            if isinstance(self, Instance):
                if self not in analysis_heap:
                    analysis_heap.write_instance_dict(self)
                instance_dict = analysis_heap.read_instance_dict(self)
                instance_dict.del_local_var(name)
            elif hasattr(self, "nl__dict__"):
                self.nl__dict__.del_load_var(name)
        else:
            if isinstance(self, Instance):
                if self not in analysis_heap:
                    analysis_heap.write_instance_dict(self)
                instance_dict = analysis_heap.read_instance_dict(self)
                instance_dict.write_local_value(name, value)
            elif hasattr(self, "nl__dict__"):
                self.nl__dict__.write_local_value(name, value)
        return descr_setters

    cls_dict = Namespace()
    local_functions = filter(
        lambda value: isinstance(value, types.FunctionType),
        locals().values(),
    )
    for function in local_functions:
        cls_dict.write_local_value(
            function.__name__,
            create_value_with_type(SpecialFunctionClass(function=function)),
        )
    cls_dict.write_local_value("nl__new__", create_value_with_type(Constructor))
    return cls_dict


class FunctionClass(metaclass=TypeMeta):
    def __init__(self, uuid, code, globals, name=None, argdefs=None, closure=None):
        self.nl__uuid__ = uuid
        self.nl__name__ = name
        self.nl__module__ = globals
        self.nl__code__ = code
        self.nl__dict__ = Namespace()

    def __le__(self, other):
        return self.nl__dict__ <= other.nl__dict__

    def __iadd__(self, other):
        self.nl__dict__ += other.nl__dict__
        return self


class SpecialFunctionClass(metaclass=TypeMeta):
    def __init__(self, *, function):
        self.nl__uuid__ = id(function)
        self.nl__name__ = function.__name__
        self.nl__code__ = function
        self.nl__dict__ = Namespace()

    def __le__(self, other):
        return self.nl__dict__ <= other.nl__dict__

    def __iadd__(self, other):
        self.nl__dict__ += other.nl__dict__
        return self

    def __call__(self, *args, **kwargs):
        return self.nl__code__(*args, **kwargs)

    def __repr__(self):
        return self.nl__name__


class MethodClass(metaclass=TypeMeta):
    def __init__(
        self,
        instance: Instance,
        function: FunctionClass,
        descr_instance=None,
        descr_owner=None,
        descr_value=None,
    ):
        self.nl__uuid__ = f"{instance.nl__uuid__}-{function.nl__uuid__}"
        self.nl__instance__ = instance
        self.nl__func__ = function
        self.nl__module__ = function.nl__module__
        self.descriptor_instance = descr_instance
        self.descriptor_owner = descr_owner
        self.descriptor_value = descr_value

    def __le__(self, other):
        return self.nl__func__ <= other.nl__func__

    def __iadd__(self, other):
        self.nl__func__ += other.nl__func__
        return self


class SpecialMethodClass(metaclass=TypeMeta):
    def __init__(
        self,
        instance: Instance,
        function: SpecialFunctionClass,
        descr_instance=None,
        descr_owner=None,
        descr_value=None,
    ):
        self.nl__uuid__ = f"{instance.nl__uuid__}-{id(function)}"
        self.nl__instance__ = instance
        self.nl__func__ = function
        self.descriptor_instance = descr_instance
        self.descriptor_owner = descr_owner
        self.descriptor_value = descr_value

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __call__(self, *args, **kwargs):
        return self.nl__func__(self.nl__instance__, *args, **kwargs)


class CustomClass(metaclass=TypeMeta):
    def __init__(self, *, uuid, name, bases, dict, module):
        self.nl__uuid__ = uuid
        self.nl__name__ = name
        self.nl__module__ = module
        self.nl__bases__ = bases
        self.nl__mro__ = c3(self)
        self.nl__dict__ = dict
        # self.nl__class__ = my_typ

    def __le__(self, other):
        return self.nl__dict__ <= other.nl__dict__

    def __iadd__(self, other):
        self.nl__dict__ += other.nl__dict__
        return self

    def __repr__(self):
        return self.nl__dict__.__repr__()


class Instance:
    def __init__(self, address, type):
        self.nl__address__ = address
        self.nl__class__ = type
        self.nl__uuid__ = f"{address}-{type.nl__uuid__}"

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __hash__(self):
        return hash(self.nl__uuid__)

    def __eq__(self, other):
        return self.nl__uuid__ == other.nl__uuid__


class IteratorClass(metaclass=TypeMeta):
    def __init__(self, iterable):
        self.nl__uuid__ = id(iterable)
        # self.nl__class__ = my_iterator

    # def __next__(self):
    #     try:
    #         res = self.internal.pop()
    #     except:
    #         res = Value()
    #     finally:
    #         return res
    #
    # cls_dict = Namespace()
    # local_functions = filter(
    #     lambda value: isinstance(value, types.FunctionType),
    #     locals().values(),
    # )
    # for function in local_functions:
    #     cls_dict.write_local_value(
    #         function.__name__,
    #         create_value_with_type(SpecialFunctionClass(function=function)),
    #     )
    # return cls_dict


class ListClass(metaclass=TypeMeta):
    def __init__(self, iterable=None):
        if iterable is None:
            self.internal = Value()
        else:
            self.internal = iterable

    def __le__(self, other):
        return self.internal <= other.internal

    def __iadd__(self, other):
        self.internal += other.internal
        return self


def _setup_BuiltinListClass():
    def __iter__(self):
        iterable = iter(self.internal.values())
        return IteratorClass(iterable)

    def append(self, x):
        self.internal.inject(x)
        print("after insert ", x, self.internal)
        return NoneType()

    def extend(self, iterable):
        self.internal.inject(iterable)
        return NoneType()

    def remove(self, x):
        return NoneType()

    def pop(self, i=None):
        return copy(self.internal)

    def clear(self):
        self.internal = Value()

    def index(self, start=None, end=None):
        return Int()

    def count(self, x):
        return Int()

    def sort(self, key=None, reverse=False):
        return NoneType()

    def reverse(self):
        return NoneType()

    def copy(self):
        internal = copy(self.internal)
        return ListClass(internal)

    cls_dict = Namespace()
    local_functions = filter(
        lambda value: isinstance(value, types.FunctionType),
        locals().values(),
    )

    for function in local_functions:
        cls_dict.write_local_value(
            function.__name__,
            create_value_with_type(SpecialFunctionClass(function=function)),
        )

    return cls_dict


class SetClass(metaclass=TypeMeta):
    def __init__(self, iterable=None):
        if iterable is None:
            self.internal = Value()
        else:
            self.internal = iterable

    def __le__(self, other):
        return self.internal <= other.internal

    def __iadd__(self, other):
        self.internal += other.internal
        return self


def _setup_BuiltinSetClass():
    def __iter__(self):
        iterable = iter(self.internal.values())
        return IteratorClass(iterable)

    def isdisjoint(self, other):
        return Bool()

    def issubset(self, other):
        return Bool()

    def union(self, other):
        assert False, self

    def intersection(self, other):
        new_value = Value()
        new_value += self.internal
        new_value += other.internal
        return SetClass(new_value)

    def difference(self, other):
        new_value = Value()
        new_value += self.internal
        new_value += other.internal
        return SetClass(new_value)

    def difference_update(self, others):
        assert False, self

    def copy(self):
        internal = copy(self.internal)
        return SetClass(internal)

    def extend(self, iterable):
        self.internal.inject_value(iterable)
        return NoneType()

    def update(self, others):
        assert False, self
        self.internal += self.internal
        return self

    def intersection_update(self, others):
        assert False, self

    def symmetric_difference_update(self, other):
        self.internal += other
        return NoneType()

    def add(self, elem):
        self.internal.inject(elem)
        return NoneType()

    def remove(self, elem):
        return NoneType()

    def discard(self, elem):
        return NoneType()

    def pop(self, i=None):
        return copy(self.internal)

    def clear(self):
        self.internal = Value()

    cls_dict = Namespace()
    local_functions = filter(
        lambda value: isinstance(value, types.FunctionType),
        locals().values(),
    )

    for function in local_functions:
        cls_dict.write_local_value(
            function.__name__,
            create_value_with_type(SpecialFunctionClass(function=function)),
        )

    return cls_dict


class FrozenSetClass(metaclass=TypeMeta):
    def __init__(self, iterable=None):
        if iterable is None:
            self.internal = Value()
        else:
            self.internal = iterable

    def __le__(self, other):
        return self.internal <= other.internal

    def __iadd__(self, other):
        self.internal += other.internal
        return self


def _setup_BuiltinFrozenSetClass():
    def __iter__(self):
        iterable = list(self.internal.values())
        return IteratorClass(iterable)

    def isdisjoint(self, other):
        return Bool()

    def issubset(self, other):
        return Bool()

    def union(self, other):
        assert False, self

    def intersection(self, other):
        new_value = Value()
        new_value += self.internal
        new_value += other.internal
        return FrozenSetClass(new_value)

    def difference(self, other):
        new_value = Value()
        new_value += self.internal
        new_value += other.internal
        return FrozenSetClass(new_value)

    def difference_update(self, others):
        assert False, self

    def copy(self):
        internal = copy(self.internal)
        return FrozenSetClass(internal)

    def extend(self, iterable):
        self.internal.inject_value(iterable)
        return NoneType()

    cls_dict = Namespace()
    local_functions = filter(
        lambda value: isinstance(value, types.FunctionType),
        locals().values(),
    )

    for function in local_functions:
        cls_dict.write_local_value(
            function.__name__,
            create_value_with_type(SpecialFunctionClass(function=function)),
        )

    return cls_dict


class TupleClass(metaclass=TypeMeta):
    def __init__(self, iterable=None):
        if iterable is None:
            self.internal = Value()
        else:
            self.internal = iterable

    def __le__(self, other):
        return self.internal <= other.internal

    def __iadd__(self, other):
        self.internal += other.internal
        return self


def _setup_BuiltinTupleClass():
    def index(self, start=None, end=None):
        return Int()

    def count(self, x):
        return Int()

    cls_dict = Namespace()
    local_functions = filter(
        lambda value: isinstance(value, types.FunctionType),
        locals().values(),
    )
    for function in local_functions:
        cls_dict.write_local_value(
            function.__name__,
            create_value_with_type(SpecialFunctionClass(function=function)),
        )
    return cls_dict


class DictClass(metaclass=TypeMeta):
    def __init__(self, keys: Value = None, values: Value = None):
        if keys is None:
            self.internal_keys = Value()
        else:
            self.internal_keys = copy(keys)

        if values is None:
            self.internal_values = Value()
        else:
            self.internal_values = copy(values)

    def __repr__(self):
        return f"keys: {self.internal_keys.__repr__()}\n values: {self.internal_values.__repr__()}"

    def __le__(self, other):
        return (
            self.internal_keys <= other.internal_keys
            and self.internal_values <= other.internal_values
        )

    def __iadd__(self, other):
        self.internal_keys += other.internal_keys
        self.internal_values += other.internal_values
        return self


def _setup_BuiltinDictClass():
    def __iter__(self):
        iterable = list(self.internal_keys.values())
        return IteratorClass(iterable)

    def clear(self):
        self.internal_keys = Value()

    def copy(self):
        internal_keys = copy(self.internal_keys)
        internal_values = copy(self.internal_values)
        return DictClass(internal_keys, internal_values)

    def fromkeys(self, iterable, value=None):
        assert False

    def get(self, key, default=None):
        res = self.internal_values
        new_value = Value()
        new_value += res
        if default is not None:
            new_value.inject(default)
        return new_value

    def items(self):
        return self.copy()

    def keys(self):
        res = self.internal_keys
        new_value = Value()
        new_value += res
        return new_value

    def pop(self, key, default=None):
        res = self.internal_values
        new_value = Value()
        new_value += res
        if default is not None:
            new_value.inject(default)
        return new_value

    def popitem(self):
        assert False, self

    def setdefault(self, key, default=None):
        if default is not None:
            self.internal_values.inject(default)
        return self.internal_values

    def update(self, other):
        assert False, self

    def values(self):
        new_value = Value()
        new_value += self.internal_values
        return new_value

    local_functions = filter(
        lambda value: isinstance(value, types.FunctionType),
        locals().values(),
    )

    cls_dict = Namespace()
    for function in local_functions:
        cls_dict.write_local_value(
            function.__name__,
            create_value_with_type(SpecialFunctionClass(function=function)),
        )
    return cls_dict


class ModuleType:
    def __init__(self, name: str, package: str | None, file: str):
        self.name = name
        self.uuid = name
        self.package = package
        self.file = file
        self.namespace = Namespace()
        self.namespace.write_special_value("__name__", name)
        self.namespace.write_special_value("__package__", package)
        self.namespace.write_special_value("__file__", file)
        self.entry_label, self.exit_label = dmf.share.create_and_update_cfg(self.file)

    def __getattr__(self, name: str) -> Value:
        if name in self.namespace:
            return self.namespace.read_value(name)
        raise AttributeError(name)


class Constructor(metaclass=TypeMeta):
    pass


def _setup_Constructor():
    def __new__(cls, *, address, type):
        return Instance(address=address, type=type)

    cls_dict = Namespace()
    local_functions = filter(
        lambda value: isinstance(value, types.FunctionType),
        locals().values(),
    )
    for function in local_functions:
        cls_dict.write_local_value(
            function.__name__,
            create_value_with_type(SpecialFunctionClass(function=function)),
        )
    return cls_dict


Constructor.nl__dict__.update(_setup_Constructor())

# we only consider form super(Class, Instance).function_call(...)
class Super(metaclass=TypeMeta):
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


def _setup_Super():
    def __init__(self, _class, _instance):
        self.nl__uuid__ = f"{_class.nl__uuid__}-{_instance.nl__uuid__}"
        instance_type = _instance.nl__class__
        self.instance_mro = instance_type.nl__mro__
        index = self.instance_mro.index(_class) + 1
        self.proxy_location = index
        self.proxy_instance = _instance

    def __getattribute__(self, name):
        res = Value()
        for cls in self.instance_mro[self.proxy_location :]:
            dict = cls.nl__dict__
            if name in dict:
                x = dict.read_value(name)
                for v in x:
                    if isinstance(v, FunctionClass):
                        method = MethodClass(instance=self.proxy_instance, function=v)
                        res.inject(method)
                    else:
                        raise NotImplementedError(v)
        assert len(res) != 0
        return res

    cls_dict = Namespace()
    local_functions = filter(
        lambda value: isinstance(value, types.FunctionType),
        locals().values(),
    )
    for function in local_functions:
        cls_dict.write_local_value(
            function.__name__,
            create_value_with_type(SpecialFunctionClass(function=function)),
        )
    return cls_dict


class Heap:
    def __init__(self):
        self.singletons: Dict[Instance, Namespace[Var, Value]] = {}

    # def __deepcopy__(self, memo):
    #     new_singletons = deepcopy(self.singletons, memo)
    #     new_heap = object.__new__(Heap)
    #     new_heap.singletons = new_singletons
    #     memo[id(self)] = new_heap
    #     return new_heap

    def __contains__(self, item):
        return item in self.singletons

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
        return "heaps: {}".format(self.singletons)

    def write_ins_to_heap(self, instance: Instance) -> Namespace:
        if instance not in self.singletons:
            self.singletons[instance] = Namespace()
        print(id(self.singletons[instance]))
        return self.singletons[instance]

    def write_field_to_heap(self, instance: Instance, field: str, value: Value):
        self.singletons[instance][LocalVar(field)] = value

    def read_field_from_heap(self, instance: Instance, field: str):
        return self.singletons[instance][LocalVar(field)]

    def read_instance_dict(self, instance: Instance):
        return self.singletons[instance]

    def write_instance_dict(self, instance: Instance):
        self.singletons[instance] = Namespace()


builtin_namespace = Namespace()

mock_value = Value()


analysis_heap = Heap()
