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
from copy import deepcopy, copy
from typing import DefaultDict

import dmf.share
from dmf.analysis.c3 import builtin_object, c3
from dmf.analysis.prim import NoneType, Int
from dmf.analysis.symboltable import Namespace
from dmf.analysis.value import Value, create_value_with_type
from dmf.analysis.variables import (
    LocalVar,
    Var,
)


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
    set_attr(obj, name, value)
    return []


def _pytype_lookup(_type, _name):
    mro = _type.__my_mro__
    for cls in mro:
        if _name in cls.__my_dict__:
            var = cls.__my_dict__.read_var(_name)
            assert isinstance(var, LocalVar)
            value: Value = cls.__my_dict__.read_value(_name)
            return value
    return None


def _all_have(value: Value, _name):
    res = []
    for typ in value:
        curr_res = my_hasattr(typ, _name)
        res.append(curr_res)
    if all(res):
        return True
    elif any(res):
        raise NotImplementedError
    else:
        return False


def dunder_lookup(typ, name: str):

    mro = typ.__my_mro__

    for cls in mro:
        if name in cls.__my_dict__:
            value = cls.__my_dict__.read_value(name)
            assert isinstance(value, Value) and len(value) == 1
            for typ in value:
                return typ
    raise AttributeError


class TypeClass:
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = object.__new__(cls)

            def __getattribute__(cls, name):
                # https://github.com/python/cpython/blob/main/Objects/typeobject.c#L4057
                # ignore meta type now

                type_of_self = self
                class_variable: Value = _pytype_lookup(type_of_self, name)

                if class_variable is not None:
                    descr_get = Value()
                    for class_type in class_variable:
                        getters = my_getattr(class_type, "__get__")
                        for getter in getters:
                            if isinstance(getter, FunctionObject):
                                descr_get.inject_type(
                                    DescriptorGetMethod(
                                        instance=class_type,
                                        function=getter,
                                        desc_instance=NoneType(),
                                        desc_owner=self,
                                    )
                                )
                            elif isinstance(getter, SpecialFunctionObject):
                                descr_get.inject_type(
                                    SpecialMethodObject(
                                        instance=class_type, function=getter
                                    )
                                )
                    if len(descr_get) > 0:
                        return descr_get

                if hasattr(self, "__my_dict__") and name in self.__my_dict__:
                    return self.__my_dict__.read_value(name)

                raise AttributeError(name)

            def __setattr__(cls, name, value):
                # https://github.com/python/cpython/blob/main/Objects/typeobject.c#L4144

                return ObjectClass.__setattr__(cls, name, value)

            self = cls.instance
            self.__my_uuid__ = id(self)
            self.__my_dict__ = Namespace()
            self.__my_bases__ = [builtin_object]
            self.__my_mro__ = c3(self)
            self.__my_class__ = self
            func = SpecialFunctionObject(func=__getattribute__)
            self.__my_dict__.write_local_value(
                __getattribute__.__name__, create_value_with_type(func)
            )
            func = SpecialFunctionObject(func=__setattr__)
            self.__my_dict__.write_local_value(
                __setattr__.__name__, create_value_with_type(func)
            )
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            memo[self_id] = self
        return memo[self_id]


class ObjectClass:
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = object.__new__(cls)

            def __init__(self):
                return self

            def __getattribute__(self, name):
                type_of_self = my_type(self)
                class_variable: Value = _pytype_lookup(type_of_self, name)

                if class_variable is not None:
                    descr_get = Value()
                    for class_type in class_variable:
                        if my_hasattr(class_type, "__set__"):
                            getters = my_getattr(class_type, "__get__")
                            descr_get.inject_value(getters)
                    if len(descr_get) > 0:
                        return descr_get

                if hasattr(self, "__my_dict__") and name in self.__my_dict__:
                    return self.__my_dict__.read_value(name)

                if class_variable is not None:
                    descr_get = Value()
                    for class_type in class_variable:
                        if isinstance(class_type, FunctionObject):
                            descr_get.inject_type(
                                MethodObject(instance=self, function=class_type)
                            )
                        elif isinstance(class_type, SpecialFunctionObject):
                            descr_get.inject_type(
                                SpecialMethodObject(instance=self, function=class_type)
                            )
                        else:
                            getters = my_getattr(class_type, "__get__")
                            for getter in getters:
                                if isinstance(getter, FunctionObject):
                                    descr_get.inject_type(
                                        DescriptorGetMethod(
                                            instance=class_type,
                                            function=getter,
                                            desc_instance=self,
                                            desc_owner=my_type(self),
                                        )
                                    )
                                elif isinstance(getter, SpecialFunctionObject):
                                    descr_get.inject_type(
                                        SpecialMethodObject(
                                            instance=class_type, function=getter
                                        )
                                    )
                                elif isinstance(getter, MethodObject):
                                    descr_get.inject_type(
                                        DescriptorGetMethod(
                                            instance=getter.__my_instance__,
                                            function=getter.__my_func__,
                                            desc_instance=self,
                                            desc_owner=my_type(self),
                                        )
                                    )

                    if len(descr_get) > 0:
                        return descr_get

                if class_variable is not None:
                    return class_variable

                raise AttributeError(name)

            def __setattr__(self, name, value):
                type_of_self = my_type(self)
                class_variable: Value = _pytype_lookup(type_of_self, name)
                if class_variable is not None:
                    descr_set = Value()
                    for class_type in class_variable:
                        setters = my_getattr(class_type, "__set__")
                        for setter in setters:
                            if isinstance(setter, FunctionObject):
                                descr_set.inject_type(
                                    DescriptorSetMethod(
                                        instance=class_type,
                                        function=setter,
                                        desc_instance=name,
                                        desc_value=value,
                                    )
                                )
                            elif isinstance(setter, SpecialFunctionObject):
                                descr_set.inject_type(
                                    SpecialMethodObject(
                                        instance=class_type, function=setter
                                    )
                                )
                        descr_set.inject_value(setters)
                    if len(descr_set) > 0:
                        return descr_set

                if isinstance(self, Instance):
                    analysis_heap.write_field_to_heap(self, name, value)
                elif hasattr(self, "__my_dict__"):
                    self.__my_dict__.write_local_value(name, value)
                return None

            self = cls.instance
            self.__my_uuid__ = id(self)
            self.__my_dict__ = Namespace()
            self.__my_bases__ = [builtin_object]
            self.__my_mro__ = c3(self)
            self.__my_class__ = my_typ
            func = SpecialFunctionObject(func=__init__)
            self.__my_dict__.write_local_value(
                __init__.__name__, create_value_with_type(func)
            )
            func = SpecialFunctionObject(func=__getattribute__)
            self.__my_dict__.write_local_value(
                __getattribute__.__name__, create_value_with_type(func)
            )
            func = SpecialFunctionObject(func=__setattr__)
            self.__my_dict__.write_local_value(
                __setattr__.__name__, create_value_with_type(func)
            )
            self.__my_dict__.write_local_value(
                "__new__", create_value_with_type(constructor)
            )
        return cls.instance

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            memo[self_id] = self
        return memo[self_id]


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

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            memo[self_id] = self
        return memo[self_id]


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

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            new_uuid = deepcopy(self.__my_uuid__, memo)
            new_name = deepcopy(self.__my_name__, memo)
            new_module = deepcopy(self.__my_module__, memo)
            new_code = deepcopy(self.__my_code__, memo)
            new_namespace = deepcopy(self.__my_dict__, memo)
            new_function_object = FunctionObject(
                new_uuid, new_name, new_module, new_code, new_namespace
            )
            memo[self_id] = new_function_object

        return memo[self_id]


class DescriptorGetFunction:
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

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            new_uuid = deepcopy(self.__my_uuid__, memo)
            new_name = deepcopy(self.__my_name__, memo)
            new_module = deepcopy(self.__my_module__, memo)
            new_code = deepcopy(self.__my_code__, memo)
            new_namespace = deepcopy(self.__my_dict__, memo)
            new_function_object = FunctionObject(
                new_uuid, new_name, new_module, new_code, new_namespace
            )
            memo[self_id] = new_function_object

        return memo[self_id]


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

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            new_func = deepcopy(self.__my_code__, memo)
            new_namespace = deepcopy(self.__my_dict__, memo)
            new_special_function_object = SpecialFunctionObject(
                func=new_func, namespace=new_namespace
            )
            memo[self_id] = new_special_function_object
        return memo[self_id]

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

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            new_instance = deepcopy(self.__my_instance__, memo)
            new_function = deepcopy(self.__my_func__, memo)
            new_method_object = MethodObject(
                instance=new_instance, function=new_function
            )
            memo[self_id] = new_method_object
        return memo[self_id]


class DescriptorGetMethod:
    def __init__(
        self,
        *,
        instance: Instance,
        function: FunctionObject,
        desc_instance,
        desc_owner,
    ):
        self.__my_uuid__ = f"{instance.__my_uuid__}-{function.__my_uuid__}"
        self.__my_instance__ = instance
        self.__my_func__ = function
        self.__my_module__ = function.__my_module__
        self.desc_instance = desc_instance
        self.desc_owner = desc_owner

    def __le__(self, other):
        return self.__my_func__ <= other.__my_func__

    def __iadd__(self, other):
        self.__my_func__ += other.__my_func__
        return self

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            new_instance = deepcopy(self.__my_instance__, memo)
            new_function = deepcopy(self.__my_func__, memo)
            new_method_object = MethodObject(
                instance=new_instance, function=new_function
            )
            memo[self_id] = new_method_object
        return memo[self_id]


class DescriptorSetMethod:
    def __init__(
        self, *, instance: Instance, function: FunctionObject, desc_instance, desc_value
    ):
        self.__my_uuid__ = f"{instance.__my_uuid__}-{function.__my_uuid__}"
        self.__my_instance__ = instance
        self.__my_func__ = function
        self.__my_module__ = function.__my_module__
        self.desc_instance = desc_instance
        self.desc_value = desc_value

    def __le__(self, other):
        return self.__my_func__ <= other.__my_func__

    def __iadd__(self, other):
        self.__my_func__ += other.__my_func__
        return self

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            new_instance = deepcopy(self.__my_instance__, memo)
            new_function = deepcopy(self.__my_func__, memo)
            new_method_object = MethodObject(
                instance=new_instance, function=new_function
            )
            memo[self_id] = new_method_object
        return memo[self_id]


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

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            new_instance = deepcopy(self.__my_instance__, memo)
            new_function = deepcopy(self.__my_func__, memo)
            new_special_method_object = SpecialMethodObject(
                instance=new_instance, function=new_function
            )
            memo[self_id] = new_special_method_object
        return memo[self_id]

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
        self_id = id(self)
        if self_id not in memo:
            uuid = deepcopy(self.__my_uuid__, memo)
            name = deepcopy(self.__my_name__, memo)
            module = deepcopy(self.__my_module__, memo)
            bases = deepcopy(self.__my_bases__, memo)
            d = deepcopy(self.__my_dict__, memo)
            custom_class = CustomClass(
                uuid=uuid, name=name, module=module, bases=bases, namespace=d
            )
            memo[self_id] = custom_class
        return memo[self_id]

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
        return Instance(address=address, cls=cls)

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            memo[self_id] = self
        return memo[self_id]


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

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            new_address = deepcopy(self.__my_address__, memo)
            new_cls = deepcopy(self.__my_class__, memo)
            new_instance = Instance(address=new_address, cls=new_cls)
            memo[self_id] = new_instance
        return memo[self_id]

    def __hash__(self):
        return hash(self.__my_uuid__)

    def __eq__(self, other):
        return self.__my_uuid__ == other.__my_uuid__


class BuiltinList:
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)

            def append(self, x: Value):
                self.internal.inject_value(x)
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

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            memo[self_id] = self
        return memo[self_id]


class BuiltinListObject:
    def __init__(self, iterable: Value = None):
        self.__my_class__ = my_list
        if iterable is None:
            self.internal = Value()
        else:
            self.internal = copy(iterable)

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            iterable = deepcopy(self.internal, memo)
            uuid = deepcopy(self.__my_uuid__, memo)
            l = BuiltinListObject(iterable)
            l.__my_uuid__ = uuid
            memo[self_id] = l
        return memo[self_id]

    def __repr__(self):
        return self.internal.__repr__()


class BuiltinTuple:
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = object.__new__(cls)

            def index(self, start=None, end=None):
                return Int()

            def count(self, x):
                return Int()

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
        return BuiltinTupleObject(iterable)

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            memo[self_id] = self
        return memo[self_id]


class BuiltinTupleObject:
    def __init__(self, iterable: Value = None):
        self.__my_class__ = my_list
        if iterable is None:
            self.internal = Value()
        else:
            self.internal = copy(iterable)

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            iterable = deepcopy(self.internal, memo)
            uuid = deepcopy(self.__my_uuid__, memo)
            l = BuiltinTupleObject(iterable)
            l.__my_uuid__ = uuid
            memo[self_id] = l
        return memo[self_id]

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
            # logger.critical("Have same name")
            pass
        else:
            self.singletons[instance] = Namespace()

    def write_field_to_heap(self, instance: Instance, field: str, value: Value):
        self.singletons[instance][LocalVar(field)] = value

    def copy(self):
        copied = Heap(self)
        return copied


builtin_namespace = Namespace()
constructor = Constructor()
analysis_heap = Heap()
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
