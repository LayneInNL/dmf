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
import sys
from typing import Tuple

from dmf.analysis.analysis_types import (
    AnalysisInstance,
    AnalysisFunction,
    AnalysisModule,
    AnalysisMethod,
    None_Instance,
    AnalysisClass,
    refine_value,
    Constructor,
    SuperArtificialClass,
    AnalysisDescriptor,
    ClassmethodAnalysisInstance,
    PropertyAnalysisInstance,
    StaticmethodAnalysisInstance,
    TypeExprVisitor,
    SuperAnalysisInstance,
)
from dmf.analysis.artificial_basic_types import (
    ArtificialClass,
    ArtificialFunction,
    ArtificialMethod,
)
from dmf.analysis.special_types import MRO_Any, Any
from dmf.analysis.typeshed_types import (
    TypeshedModule,
    TypeshedInstance,
    Typeshed,
    TypeshedClass,
)
from dmf.analysis.value import Value, type_2_value
from dmf.log.logger import logger


def _py_type(obj):
    return obj.tp_class


def _pytype_lookup(obj_type, name, mros=None) -> Value:
    res = _find_name_in_mro(obj_type, name, mros)
    return res


def _pytype_lookup_set(type, name, value):
    res = _find_name_in_mro(type, name)

    # no class variable called name
    if len(res) == 0:
        type.tp_dict.write_local_value(name, value)
        return type.tp_dict.read_value(name)
    # class variable exists, return this one
    else:
        res.inject(value)
        return res


def _find_name_in_mro(obj_type, name, mros=None) -> Value:
    all_mro_value = Value()
    if mros is not None:
        tp_mros = mros
    else:
        tp_mros = obj_type.tp_mro

    for tp_mro in tp_mros:
        for cls in tp_mro:
            if cls is MRO_Any:
                return Value.make_any()
            elif cls is Any:
                return Value.make_any()
            else:
                # tp_dict could belong to AnalysisClass, ArtificialClass and
                # TypeshedClass
                if name not in cls.tp_dict:
                    if hasattr(cls, "tp_fallback"):
                        fallback_clses = cls.tp_fallback
                        for one_fallback in fallback_clses:
                            if name in one_fallback.tp_dict:
                                curr_mro_value = one_fallback.tp_dict.read_value(name)
                                all_mro_value.inject(curr_mro_value)
                                break

                else:
                    curr_mro_value = cls.tp_dict.read_value(name)
                    all_mro_value.inject(curr_mro_value)
                    break

    return all_mro_value


# simulate builtins.getattr, but operate on a set of objects
def analysis_getattrs(objs: Value, name: str, default=None) -> Value:
    # if objs is Any, just return two Anys
    if objs.is_Any():
        return Value.make_any()

    # direct results
    direct_res = Value()

    for obj in objs:
        curr_direct_res = analysis_getattr(obj, name)
        direct_res += curr_direct_res

    # add default to direct_res
    if default is not None:
        direct_res.inject(default)

    return direct_res


def setattrs(objs, name, value) -> Value:
    # if objs is Any, return Any
    if objs.is_Any():
        return Value.make_any()

    descr_sets = Value()
    for obj in objs:
        curr_descr_sets = _setattr(obj, name, value)
        descr_sets += curr_descr_sets

    return descr_sets


def _setattr(obj, name, value) -> Value:
    tp = _py_type(obj)
    if isinstance(obj, AnalysisInstance):
        return GenericSetAttr(obj, name, value)
    elif isinstance(obj, AnalysisClass):
        return type_setattro(obj, name, value)
    elif isinstance(obj, AnalysisFunction):
        return GenericSetAttr(obj, name, value)
    raise NotImplementedError(f"setattr({obj},{name},{value})")
    # # work on class
    # if isinstance(obj, ClassLevel):
    #     return type_setattro(obj, name, value)
    # else:
    #     raise NotImplementedError(f"setattr({obj},{name},{value})")
    # else:
    #     return Value(any=True)

    return value


def analysis_getattr(obj, name) -> Value:
    return_value = Value()
    if obj is Any:
        return Value.make_any()
    elif isinstance(obj, (AnalysisModule, TypeshedModule)):
        one_return = obj.custom_getattr(name)
        return one_return
    elif isinstance(obj, (AnalysisInstance, TypeshedInstance)):
        one_return = GenericGetAttr(obj, name)
        return one_return
    elif isinstance(obj, (AnalysisClass, ArtificialClass)):
        one_return = type_getattro(obj, name)
        return one_return
    # work on class
    elif isinstance(obj, AnalysisFunction):
        return GenericGetAttr(obj, name)
    elif isinstance(obj, TypeshedClass):
        one_return = type_getattro(obj, name)
        return one_return
    else:
        raise NotImplementedError(obj)


def GenericGetAttr(obj, name):
    return_value = Value()

    # get types of obj
    obj_type = _py_type(obj)
    mros = None
    if isinstance(obj, SuperAnalysisInstance):
        obj = obj.tp_self
        mros = obj.tp_mro
        obj_type = _py_type(obj)

    # try finding descriptors
    class_variables = _pytype_lookup(obj_type, name, mros)

    # traverse descrs
    for class_variable in class_variables:
        # if descr is a function, there is an implicit __set__
        if isinstance(class_variable, AnalysisFunction):
            one_value = AnalysisMethod(tp_function=class_variable, tp_instance=obj)
            return_value.inject(one_value)
        # if descr is a function, there is an implicit __set__
        elif isinstance(class_variable, ArtificialFunction):
            one_value = ArtificialMethod(tp_function=class_variable, tp_instance=obj)
            return_value.inject(one_value)
        # if descr is a typeshed, we already know its information.
        # So we have to translate it into abstract value
        # @property def test(): int, in this case we extract int
        # def test(): int, in this case we extract test function
        elif isinstance(class_variable, Typeshed):
            return_value.inject(class_variable)
        else:
            # go through normal cases
            class_variable_type = _py_type(class_variable)
            if isinstance(class_variable, PropertyAnalysisInstance):
                fgets = class_variable.tp_dict.read_value(
                    class_variable.tp_container[0]
                )
                for fget in fgets:
                    obj_value = type_2_value(obj)
                    one_value = AnalysisDescriptor(fget, obj_value)
                    return_value.inject(one_value)
            elif isinstance(class_variable, ClassmethodAnalysisInstance):
                functions = class_variable.tp_dict.read_value(
                    class_variable.tp_container
                )
                for function in functions:
                    one_res = AnalysisMethod(tp_function=function, tp_instance=obj_type)
                    return_value.inject(one_res)
            elif isinstance(class_variable, StaticmethodAnalysisInstance):
                functions = class_variable.tp_dict.read_value(
                    class_variable.tp_container
                )
                for function in functions:
                    return_value.inject(function)
            else:
                # normal __get__ lookup, only AnalysisClass is considered
                if not isinstance(class_variable_type, AnalysisClass):
                    logger.info(f"{class_variable_type} is not an AnalysisClass")
                    continue

                class_variable_type_gets = _pytype_lookup(
                    class_variable_type, "__get__"
                )
                for class_variable_type_get in class_variable_type_gets:
                    # descr_tp_get must be AnalysisFunction
                    if isinstance(class_variable_type_get, AnalysisFunction):
                        descr_value = type_2_value(class_variable)
                        obj_value = type_2_value(obj)
                        obj_type_value = type_2_value(obj_type)
                        one_value = AnalysisDescriptor(
                            class_variable_type_get,
                            descr_value,
                            obj_value,
                            obj_type_value,
                        )
                        return_value.inject(one_value)
                    else:
                        raise NotImplementedError(f"{obj},{name}")

    tp_dict = obj.tp_dict
    if name in obj.tp_dict:
        one_res = tp_dict.read_value(name)
        return_value.inject(one_res)

    return_value.inject(class_variables)

    return_value = refine_value(return_value)

    return return_value


def type_getattro(type, name) -> Value:
    return_value = Value()

    class_variables = _pytype_lookup(type, name)
    for class_variable in class_variables:
        # the __get__ of function is id.
        if isinstance(class_variable, (AnalysisFunction, ArtificialFunction)):
            return_value.inject(class_variable)
        elif isinstance(class_variable, Typeshed):
            curr_visitor = TypeExprVisitor(class_variable)
            curr_value = curr_visitor.refine()
            return_value.inject(curr_value)
        elif isinstance(class_variable, Constructor):
            return_value.inject(class_variable)
        # property object itself
        elif isinstance(class_variable, PropertyAnalysisInstance):
            return_value.inject(class_variable)
        # classmethod object
        elif isinstance(class_variable, ClassmethodAnalysisInstance):
            functions = class_variable.tp_dict.read_value(class_variable.tp_container)
            for function in functions:
                one_res = AnalysisMethod(
                    tp_function=function, tp_instance=class_variable
                )
                return_value.inject(one_res)
        # static method object
        elif isinstance(class_variable, StaticmethodAnalysisInstance):
            functions = class_variable.tp_dict.read_value(class_variable.tp_container)
            for function in functions:
                return_value.inject(function)
        else:
            class_variable_type = _py_type(class_variable)
            class_variable_type_gets = _pytype_lookup(class_variable_type, "__get__")
            for class_variable_type_get in class_variable_type_gets:
                if isinstance(class_variable_type_get, AnalysisFunction):
                    descr_value = type_2_value(class_variable)
                    obj_value = type_2_value(None_Instance)
                    obj_type_value = type_2_value(type)
                    one_descr = AnalysisDescriptor(
                        class_variable_type_get, descr_value, obj_value, obj_type_value
                    )
                    return_value.inject(one_descr)
                else:
                    return_value.inject(class_variable_type_get)

    if name in type.tp_dict:
        one_res = type.tp_dict.read_value(name)
        return_value.inject(one_res)

    return_value.inject(class_variables)

    return return_value


def GenericDelAttr(obj, name):
    descr_value = Value()

    obj_type = _py_type(obj)
    # look up class dict
    class_variables = _pytype_lookup(obj_type, name)
    for class_variable in class_variables:
        # check property instance
        if isinstance(class_variable, PropertyAnalysisInstance):
            # delattr
            fdels = class_variable.tp_dict.read_value(class_variable.tp_container[2])
            for fdel in fdels:
                obj_value = type_2_value(obj)
                one_value = AnalysisDescriptor(fdel, obj_value)
                descr_value.inject(one_value)
        else:
            class_variable_type = _py_type(class_variable)
            if not isinstance(class_variable_type, AnalysisClass):
                logger.info(f"{class_variable_type} is not class")
                continue

            # check if there is a __delete__
            descriptor_type_dels = _pytype_lookup(class_variable_type, "__delete__")
            for descriptor_type_del in descriptor_type_dels:
                if isinstance(descriptor_type_del, AnalysisFunction):
                    descr_value = type_2_value(class_variables)
                    obj_value = type_2_value(obj)
                    one_descr = AnalysisDescriptor(
                        descriptor_type_del, descr_value, obj_value
                    )
                    descr_value.inject(one_descr)
                else:
                    raise NotImplementedError(descriptor_type_del)

    return descr_value


def GenericSetAttr(obj, name, value):
    if value is None:
        return GenericDelAttr(obj, name)
    descr_value = Value()

    obj_type = _py_type(obj)
    # look up class dict
    class_variables = _pytype_lookup(obj_type, name)
    for class_variable in class_variables:
        # check property instance
        if isinstance(class_variable, PropertyAnalysisInstance):
            # setattr
            fsets = class_variable.tp_dict.read_value(class_variable.tp_container[1])
            for fset in fsets:
                obj_value = type_2_value(obj)
                value_value = value
                one_value = AnalysisDescriptor(fset, obj_value, value_value)
                descr_value.inject(one_value)
        else:
            class_variable_type = _py_type(class_variable)
            if not isinstance(class_variable_type, AnalysisClass):
                logger.info(f"{class_variable_type} is not class")
                continue

            # check if there is a __set__
            descriptor_type_dels = _pytype_lookup(class_variable_type, "__set__")
            for descriptor_type_del in descriptor_type_dels:
                if isinstance(descriptor_type_del, AnalysisFunction):
                    descr_value = type_2_value(class_variables)
                    obj_value = type_2_value(obj)
                    value_value = value
                    one_descr = AnalysisDescriptor(
                        descriptor_type_del, descr_value, obj_value, value_value
                    )
                    descr_value.inject(one_descr)
                else:
                    raise NotImplementedError(descriptor_type_del)

    if name not in obj.tp_dict:
        obj.tp_dict.write_local_value(name, value)
    else:
        union_value = Value()
        prev_value = obj.tp_dict.read_value(name)
        union_value.inject(prev_value)
        union_value.inject(value)
        # instance dict assignment
        obj.tp_dict.write_local_value(name, union_value)

    return descr_value


def type_delattro(type, name):
    pass


def type_setattro(type, name, value):
    return GenericSetAttr(type, name, value)
