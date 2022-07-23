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

import types
from collections import defaultdict
from copy import copy, deepcopy
from typing import DefaultDict, Dict

import dmf.share
from dmf.analysis.c3 import c3
from dmf.analysis.prim import NoneType, Int
from dmf.analysis.namespace import Namespace
from dmf.analysis.value import Value, create_value_with_type
from dmf.analysis.variables import (
    LocalVar,
    Var,
)


def Type(obj):
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


def my_setattr(obj, name, value):
    set_attr = dunder_lookup(Type(obj), "__setattr__")
    res = set_attr(obj, name, value)
    return res


def _pytype_lookup(_type, _name):
    mro = _type.__my_mro__
    for cls in mro:
        if _name in cls.__my_dict__:
            var = cls.__my_dict__.read_var_type(_name)
            assert isinstance(var, LocalVar)
            value: Value = cls.__my_dict__.read_value(_name)
            return value
    return None


def dunder_lookup(typ, name: str):

    mro = typ.__my_mro__

    for cls in mro:
        if name in cls.__my_dict__:
            value = cls.__my_dict__.read_value(name)
            assert isinstance(value, Value) and len(value) == 1
            for typ in value:
                return typ
    raise AttributeError


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super(Singleton, cls).__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class Base:
    def __init__(self):
        setattr(self, "__my_dict__", Namespace())


class TypeClass(Base, metaclass=Singleton):
    # instance = None

    def __custom__(self):
        def __getattribute__(type, name):
            metatype = Type(type)

            meta_attribute = _pytype_lookup(metatype, name)
            if meta_attribute is not None:
                assert False, meta_attribute

            attribute = _pytype_lookup(type, name)
            cls_vars = attribute
            if cls_vars is not None:
                descr_get = Value()
                for cls_var in cls_vars:
                    cls_var_type = Type(cls_var)
                    if isinstance(cls_var, FunctionObject):
                        descr_get.inject(cls_var)
                    elif isinstance(cls_var, SpecialFunctionObject):
                        descr_get.inject(cls_var)
                    else:
                        assert False, cls_var
                if len(descr_get) > 0:
                    return descr_get

            assert False, type
            raise AttributeError(name)

        def __setattr__(type, name, value):
            cls_vars: Value = _pytype_lookup(type, name)
            descr_setters = Value()
            if cls_vars is not None:
                for cls_var in cls_vars:
                    cls_var_type = Type(cls_var)
                    setters = _pytype_lookup(cls_var_type, "__set__")
                    for setter in setters:
                        if isinstance(setter, FunctionObject):
                            descr_setters.inject(
                                MethodObject(
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
                elif hasattr(self, "__my_dict__"):
                    self.__my_dict__.del_load_var(name)
            else:
                if isinstance(self, Instance):
                    if self not in analysis_heap:
                        analysis_heap.write_instance_dict(self)
                    instance_dict = analysis_heap.read_instance_dict(self)
                    instance_dict.write_local_value(name, value)
                elif hasattr(self, "__my_dict__"):
                    self.__my_dict__.write_local_value(name, value)
            return descr_setters

        func = SpecialFunctionObject(func=__getattribute__)
        self.__my_dict__.write_local_value(
            __getattribute__.__name__, create_value_with_type(func)
        )
        func = SpecialFunctionObject(func=__setattr__)
        self.__my_dict__.write_local_value(
            __setattr__.__name__, create_value_with_type(func)
        )

    def __init__(self):
        super().__init__()
        self.__my_uuid__ = id(self)
        self.__my_bases__ = [object()]
        self.__my_mro__ = c3(self)
        self.__my_class__ = self
        self.__custom__()

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class ObjectClass:
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = object.__new__(cls)

            def __init__(self):
                return self

            def __getattribute__(self, name):
                # type_of_self = type(self)
                type_of_self = Type(self)
                # get class variables
                cls_vars: Value = _pytype_lookup(type_of_self, name)

                if cls_vars is not None:
                    data_descr_getters = Value()
                    for cls_var in cls_vars:
                        cls_var_type = Type(cls_var)
                        descr_getters = _pytype_lookup(cls_var_type, "__get__")
                        if descr_getters is not None:
                            descr_setters = _pytype_lookup(cls_var_type, "__set__")
                            if descr_setters is not None:
                                for getter in descr_getters:
                                    if isinstance(getter, FunctionObject):
                                        method_getter = MethodObject(
                                            instance=cls_var,
                                            function=getter,
                                            descr_instance=self,
                                            descr_owner=type_of_self,
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
                elif hasattr(self, "__my_dict__") and name in self.__my_dict__:
                    return self.__my_dict__.read_value(name)

                if cls_vars is not None:
                    nondata_descr_getters = Value()
                    for cls_var in cls_vars:
                        if isinstance(cls_var, FunctionObject):
                            nondata_descr_getters.inject(
                                MethodObject(instance=self, function=cls_var)
                            )
                        elif isinstance(cls_var, SpecialFunctionObject):
                            nondata_descr_getters.inject(
                                SpecialMethodObject(instance=self, function=cls_var)
                            )
                        else:
                            cls_var_type = Type(cls_var)
                            descr_getters = _pytype_lookup(cls_var_type, "__get__")
                            if descr_getters is not None:
                                for getter in descr_getters:
                                    if isinstance(getter, FunctionObject):
                                        method_getter = MethodObject(
                                            instance=cls_var,
                                            function=getter,
                                            descr_instance=self,
                                            descr_owner=type_of_self,
                                        )
                                        nondata_descr_getters.inject(method_getter)
                                    else:
                                        assert False, getter
                    if len(nondata_descr_getters) > 0:
                        return nondata_descr_getters
                if cls_vars is not None:
                    return cls_vars

                raise AttributeError(name)

            def __setattr__(self, name, value):
                self_type = Type(self)
                cls_vars: Value = _pytype_lookup(self_type, name)

                descr_setters = Value()
                if cls_vars is not None:
                    for cls_var in cls_vars:
                        cls_var_type = Type(cls_var)
                        setters = _pytype_lookup(cls_var_type, "__set__")
                        for setter in setters:
                            if isinstance(setter, FunctionObject):
                                descr_setters.inject(
                                    MethodObject(
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
                    elif hasattr(self, "__my_dict__"):
                        self.__my_dict__.del_load_var(name)
                else:
                    if isinstance(self, Instance):
                        if self not in analysis_heap:
                            analysis_heap.write_instance_dict(self)
                        instance_dict = analysis_heap.read_instance_dict(self)
                        instance_dict.write_local_value(name, value)
                    elif hasattr(self, "__my_dict__"):
                        self.__my_dict__.write_local_value(name, value)
                return descr_setters

            cls.instance.__my_dict__ = Namespace()
            func = SpecialFunctionObject(func=__init__)
            cls.instance.__my_dict__.write_local_value(
                __init__.__name__, create_value_with_type(func)
            )
            func = SpecialFunctionObject(func=__getattribute__)
            cls.instance.__my_dict__.write_local_value(
                __getattribute__.__name__, create_value_with_type(func)
            )
            func = SpecialFunctionObject(func=__setattr__)
            cls.instance.__my_dict__.write_local_value(
                __setattr__.__name__, create_value_with_type(func)
            )
            cls.instance.__my_dict__.write_local_value(
                "__new__", create_value_with_type(constructor)
            )
        return cls.instance

    def __init__(self):
        self.__my_uuid__ = id(self)
        self.__my_bases__ = [object()]
        self.__my_mro__ = c3(self)
        self.__my_class__ = my_typ

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class FunctionClass:
    instance = None

    def __new__(cls):
        if cls.instance is None:
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
    def __init__(self, uuid, name, module, code, namespace=None):
        self.__my_uuid__ = uuid
        self.__my_name__ = name
        self.__my_module__ = module
        self.__my_code__ = code
        if namespace is None:
            self.__my_dict__ = Namespace()
        else:
            self.__my_dict__ = namespace
        self.__my_class__ = my_function

    def __le__(self, other):
        return self.__my_dict__ <= other.__my_dict__

    def __iadd__(self, other):
        self.__my_dict__ += other.__my_dict__
        return self


class SpecialFunctionObject:
    def __init__(self, *, func, namespace=None):
        self.__my_uuid__ = str(id(func))
        self.__my_name__ = func.__name__
        self.__my_code__ = func
        if namespace is None:
            self.__my_dict__ = Namespace()
        else:
            self.__my_dict__ = namespace

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
    def __init__(
        self,
        *,
        instance: Instance,
        function: FunctionObject,
        descr_instance=None,
        descr_owner=None,
        descr_value=None,
    ):
        self.__my_uuid__ = f"{instance.__my_uuid__}-{function.__my_uuid__}"
        self.__my_instance__ = instance
        self.__my_func__ = function
        self.__my_module__ = function.__my_module__
        self.descriptor_instance = descr_instance
        self.descriptor_owner = descr_owner
        self.descriptor_value = descr_value

    def __le__(self, other):
        return self.__my_func__ <= other.__my_func__

    def __iadd__(self, other):
        self.__my_func__ += other.__my_func__
        return self


class SpecialMethodObject:
    def __init__(
        self,
        *,
        instance: Instance,
        function: SpecialFunctionObject,
        descr_instance=None,
        descr_owner=None,
        descr_value=None,
    ):
        self.__my_uuid__ = f"{instance.__my_uuid__}-{id(function)}"
        self.__my_name__ = function.__my_name__
        self.__my_instance__ = instance
        self.__my_func__ = function
        self.descriptor_instance = descr_instance
        self.descriptor_owner = descr_owner
        self.descriptor_value = descr_value

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

    def __repr__(self):
        return self.__my_dict__.__repr__()


class Constructor:
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)
            cls.instance.__my_uuid__ = id(cls.instance)
        return cls.instance

    def __call__(self, address, cls):
        return Instance(addr=address, cls=cls)

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class Instance:
    def __init__(self, addr, cls):
        self.__my_address__ = addr
        self.__my_class__ = cls
        self.__my_uuid__ = f"{addr}-{cls.__my_uuid__}"

    def __le__(self, other: Instance):
        return True

    def __iadd__(self, other: Instance):
        return self

    def __hash__(self):
        return hash(self.__my_uuid__)

    def __eq__(self, other):
        return self.__my_uuid__ == other.__my_uuid__

    # def __deepcopy__(self, memo):
    #     new_addr = deepcopy(self.__my_address__, memo)
    #     new_class = deepcopy(self.__my_class__, memo)
    #     new_heap = deepcopy(self.__my_dict__, memo)
    #     new_instance = Instance(new_addr, new_class)
    #     new_instance.__my_dict__ = new_heap
    #     memo[id(self)] = new_instance
    #     return memo[id(self)]


class Iterator:
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)

            def __next__(self):
                try:
                    res = self.iterable.pop()
                    if isinstance(res, Int):
                        print("int")
                    print("popped value", res)
                except:
                    res = Value()
                finally:
                    return res

            cls.instance.__my_uuid__ = id(cls.instance)
            cls.instance.__my_bases__ = [my_object]
            cls.instance.__my_mro__ = c3(cls.instance)

            local_functions = filter(
                lambda value: isinstance(value, types.FunctionType),
                locals().values(),
            )

            cls.instance.__my_dict__ = Namespace()
            for function in local_functions:
                cls.instance.__my_dict__.write_local_value(
                    function.__name__,
                    create_value_with_type(SpecialFunctionObject(func=function)),
                )

        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class IteratorObject:
    def __init__(self, iterable):
        self.__my_uuid__ = id(iterable)
        self.__my_class__ = my_iterator
        self.iterable = iterable

    def __le__(self, other):
        return len(self.iterable) == len(other.iterable)

    def __iadd__(self, other):
        return self


class BuiltinList:
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)

            def __iter__(self):
                iterable = list(self.internal.values())
                return IteratorObject(iterable)

            def append(self, x: Value):
                self.internal.inject_value(x)
                print("after insert ", x, self.internal)
                return NoneType()

            def extend(self, iterable):
                self.internal.inject_value(iterable)
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
                return BuiltinListObject(internal)

            cls.instance.__my_uuid__ = id(cls.instance)
            cls.instance.__my_bases__ = [my_object]
            cls.instance.__my_mro__ = c3(cls.instance)

            local_functions = filter(
                lambda value: isinstance(value, types.FunctionType),
                locals().values(),
            )

            cls.instance.__my_dict__ = Namespace()
            for function in local_functions:
                cls.instance.__my_dict__.write_local_value(
                    function.__name__,
                    create_value_with_type(SpecialFunctionObject(func=function)),
                )

        return cls.instance

    def __call__(self, iterable: Value = None):
        return BuiltinListObject(iterable)

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class BuiltinListObject:
    def __init__(self, iterable: Value = None):
        self.__my_class__ = my_list
        if iterable is None:
            self.internal = Value()
        else:
            self.internal = copy(iterable)

    def __repr__(self):
        return self.internal.__repr__()

    def __le__(self, other):
        return self.internal <= other.internal

    def __iadd__(self, other):
        self.internal += other.internal
        return self


class BuiltinTuple:
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)

            def index(self, start=None, end=None):
                return Int()

            def count(self, x):
                return Int()

            local_functions = filter(
                lambda value: isinstance(value, types.FunctionType),
                locals().values(),
            )

            cls.instance.__my_dict__ = Namespace()
            for function in local_functions:
                cls.instance.__my_dict__.write_local_value(
                    function.__name__,
                    create_value_with_type(SpecialFunctionObject(func=function)),
                )

        return cls.instance

    def __init__(self):
        self.instance.__my_uuid__ = id(self.instance)
        self.instance.__my_bases__ = [my_object]
        self.instance.__my_mro__ = c3(self.instance)

    def __call__(self, iterable: Value = None):
        return BuiltinTupleObject(iterable)

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class BuiltinTupleObject:
    def __init__(self, iterable: Value = None):
        self.__my_class__ = my_list
        if iterable is None:
            self.internal = Value()
        else:
            self.internal = copy(iterable)

    def __repr__(self):
        return self.internal.__repr__()


class ModuleType:
    def __init__(self, name: str, package: str | None, file: str):
        self.name = name
        self.uuid = name
        self.package = package
        self.file = file
        self.namespace = Namespace()
        self.namespace.write_helper_value("__name__", name)
        self.namespace.write_helper_value("__package__", package)
        self.namespace.write_helper_value("__file__", file)
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
constructor = Constructor()
my_typ = TypeClass()
my_object = ObjectClass()
my_list = BuiltinList()
my_tuple = BuiltinTuple()

v = create_value_with_type(my_object)
builtin_namespace.write_local_value("object", v)
v = create_value_with_type(my_list)
builtin_namespace.write_local_value("list", v)
v = create_value_with_type(my_tuple)
builtin_namespace.write_local_value("tuple", v)

my_function = FunctionClass()
mock_value = Value()

my_iterator = Iterator()

analysis_heap = Heap()
