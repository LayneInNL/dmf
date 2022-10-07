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

import sys

from dmf.analysis.analysis_types import (
    AnalysisInstance,
    AnalysisFunction,
    AnalysisModule,
    AnalysisMethod,
    None_Instance,
    AnalysisClass,
    refine_value,
    Constructor,
    AnalysisDescriptor,
    ClassmethodAnalysisInstance,
    PropertyAnalysisInstance,
    StaticmethodAnalysisInstance,
    SuperAnalysisInstance,
)
from dmf.analysis.artificial_basic_types import (
    ArtificialClass,
    ArtificialFunction,
    ArtificialMethod,
)
from dmf.analysis.special_types import Any
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


def _find_name_in_mro(obj_type, name, mros=None) -> Value:
    all_mro_value = Value()
    if mros is not None:
        tp_mros = mros
    else:
        tp_mros = obj_type.tp_mro

    for tp_mro in tp_mros:
        for cls in tp_mro:
            if cls is Any:
                return Value.make_any()
            else:
                # tp_dict could belong to AnalysisClass, ArtificialClass and
                # TypeshedClass
                if not cls.tp_dict.contains(name):
                    if hasattr(cls, "tp_fallback"):
                        fallback_clses = cls.tp_fallback
                        one_fallback = fallback_clses.extract_1_elt()
                        if one_fallback.tp_dict.contains(name):
                            curr_mro_value = one_fallback.tp_dict.read_value(name)
                            all_mro_value.inject(curr_mro_value)
                            break
                else:
                    curr_mro_value = cls.tp_dict.read_value(name)
                    all_mro_value.inject(curr_mro_value)
                    break

    return all_mro_value


# simulate builtins.getattr, but operate on a set of objects
def getattrs(objs: Value, name: str) -> Value:
    if objs.is_any():
        return Value.make_any()

    direct_res = Value()
    for obj in objs:
        curr_direct_res = analysis_getattr(obj, name)
        direct_res += curr_direct_res

    return direct_res


def setattrs(objs: Value, name: str, value: Value | None) -> Value:
    if objs.is_any():
        return Value.make_any()

    descr_sets = Value()
    for obj in objs:
        curr_descr_sets = analysis_setattr(obj, name, value)
        descr_sets += curr_descr_sets

    return descr_sets


def analysis_getattr(obj, name: str) -> Value:
    if obj is Any:
        return Value.make_any()
    elif isinstance(obj, (AnalysisModule, TypeshedModule)):
        one_return = obj.custom_getattr(name)
        return one_return
    elif isinstance(obj, (AnalysisInstance, TypeshedInstance)):
        one_return = GenericGetAttr(obj, name)
        return one_return
    elif isinstance(obj, (AnalysisClass, ArtificialClass, TypeshedClass)):
        one_return = type_getattro(obj, name)
        return one_return
    # work on class
    elif isinstance(obj, AnalysisFunction):
        return obj.tp_dict.read_value(name)
    else:
        raise NotImplementedError(f"analysis_getattr ({obj},{name})")


def type_getattro(obj, name: str):
    if sys.analysis_type == "crude":
        return type_getattro_Crude(obj, name)
    elif sys.analysis_type == "refined":
        res, kind = type_getattro_Refined(obj, name)
        if kind == -1:
            return type_getattro_Crude(obj, name)
        else:
            return res


def GenericGetAttr(obj, name: str) -> Value:
    if sys.analysis_type == "crude":
        return GenericGetAttr_Crude(obj, name)
    elif sys.analysis_type == "refined":
        res, kind = GenericGetAttr_Refined(obj, name)
        if kind == -1:
            return GenericGetAttr_Crude(obj, name)
        else:
            return res
    else:
        raise NotImplementedError


def GenericGetAttr_Refined(obj, name: str):
    # get types of obj
    obj_type = _py_type(obj)

    # deal with super()
    # super is like a proxy object
    mros = None
    if isinstance(obj, SuperAnalysisInstance):
        mros = obj.tp_mro
        obj = obj.tp_self
        obj_type = _py_type(obj)

    return_value = Value()
    # try finding descriptors
    class_variables = _pytype_lookup(obj_type, name, mros)
    if class_variables.is_any():
        return Value.make_any(), -1

    if len(class_variables):
        for cls_var in class_variables:
            # if descr is a function, there is an implicit __get__
            if isinstance(
                cls_var,
                (
                    AnalysisFunction,
                    ArtificialFunction,
                    ClassmethodAnalysisInstance,
                    StaticmethodAnalysisInstance,
                ),
            ):
                break
            elif isinstance(cls_var, PropertyAnalysisInstance):
                fgets = cls_var.tp_dict.read_value(cls_var.tp_container[0])
                fget = fgets.extract_1_elt()
                obj_value = type_2_value(obj)
                one_value = AnalysisDescriptor(fget, obj_value)
                return_value.inject(one_value)
            # if descr is a typeshed, we already know its information.
            # So we have to translate it into abstract value
            # @property def test(): int, in this case we extract int
            # def test(): int, in this case we extract test function
            elif isinstance(cls_var, Typeshed):
                return Value.make_any(), -1
            else:
                break
        else:
            return_value = refine_value(return_value)
            return return_value, 1

    # step 2, instance dict
    return_value = Value()
    if name in obj.tp_dict:
        one_res = obj.tp_dict.read_value(name)
        return_value.inject(one_res)
        return_value = refine_value(return_value)
        return return_value, 2

    # step 3, non-data descriptor
    return_value = Value()
    if class_variables:
        for cls_var in class_variables:
            # if descr is a function, there is an implicit __get__
            if isinstance(cls_var, AnalysisFunction):
                one_value = AnalysisMethod(tp_function=cls_var, tp_instance=obj)
                return_value.inject(one_value)
            # if descr is an artificial function, there is an implicit __get__
            elif isinstance(cls_var, ArtificialFunction):
                one_value = ArtificialMethod(tp_function=cls_var, tp_instance=obj)
                return_value.inject(one_value)
            elif isinstance(cls_var, PropertyAnalysisInstance):
                fgets = cls_var.tp_dict.read_value(cls_var.tp_container[0])
                fget = fgets.extract_1_elt(fgets)
                obj_value = type_2_value(obj)
                one_value = AnalysisDescriptor(fget, obj_value)
                return_value.inject(one_value)
            elif isinstance(cls_var, ClassmethodAnalysisInstance):
                functions = cls_var.tp_dict.read_value(cls_var.tp_container)
                for function in functions:
                    one_res = AnalysisMethod(tp_function=function, tp_instance=obj_type)
                    return_value.inject(one_res)
            elif isinstance(cls_var, StaticmethodAnalysisInstance):
                functions = cls_var.tp_dict.read_value(cls_var.tp_container)
                for function in functions:
                    return_value.inject(function)
            # if descr is a typeshed, we already know its information.
            # So we have to translate it into abstract value
            # @property def test(): int, in this case we extract int
            # def test(): int, in this case we extract test function
            elif isinstance(cls_var, Typeshed):
                return Value.make_any(), -1
            else:
                break
        else:
            return_value = refine_value(return_value)
            return return_value, 3

    # step 4, class dict
    return_value = Value()
    return_value.inject(class_variables)
    return_value = refine_value(return_value)
    return return_value, 4


def GenericGetAttr_Crude(obj, name):
    return_value = Value()

    # get types of obj
    obj_type = _py_type(obj)

    # deal with super()
    # super is like a proxy object
    mros = None
    if isinstance(obj, SuperAnalysisInstance):
        mros = obj.tp_mro
        obj = obj.tp_self
        obj_type = _py_type(obj)

    # try finding descriptors
    class_variables = _pytype_lookup(obj_type, name, mros)
    for cls_var in class_variables:
        # if descr is a function, there is an implicit __get__
        if isinstance(cls_var, AnalysisFunction):
            one_value = AnalysisMethod(tp_function=cls_var, tp_instance=obj)
            return_value.inject(one_value)
        # if descr is an artificial function, there is an implicit __get__
        elif isinstance(cls_var, ArtificialFunction):
            one_value = ArtificialMethod(tp_function=cls_var, tp_instance=obj)
            return_value.inject(one_value)
        elif isinstance(cls_var, PropertyAnalysisInstance):
            fgets = cls_var.tp_dict.read_value(cls_var.tp_container[0])
            for fget in fgets:
                obj_value = type_2_value(obj)
                one_value = AnalysisDescriptor(fget, obj_value)
                return_value.inject(one_value)
        elif isinstance(cls_var, ClassmethodAnalysisInstance):
            functions = cls_var.tp_dict.read_value(cls_var.tp_container)
            for function in functions:
                one_res = AnalysisMethod(tp_function=function, tp_instance=obj_type)
                return_value.inject(one_res)
        elif isinstance(cls_var, StaticmethodAnalysisInstance):
            functions = cls_var.tp_dict.read_value(cls_var.tp_container)
            for function in functions:
                return_value.inject(function)
        # if descr is a typeshed, we already know its information.
        # So we have to translate it into abstract value
        # @property def test(): int, in this case we extract int
        # def test(): int, in this case we extract test function
        elif isinstance(cls_var, Typeshed):
            return_value.inject(cls_var)
        else:
            return_value.inject(cls_var)

    if obj.tp_dict.contains(name):
        one_res = obj.tp_dict.read_value(name)
        return_value.inject(one_res)

    return_value.inject(class_variables)
    return_value = refine_value(return_value)

    return return_value


def type_getattro_Crude(type, name: str) -> Value:
    return_value = Value()

    class_variables = _pytype_lookup(type, name)
    if class_variables.is_any():
        return Value.make_any()

    for class_variable in class_variables:
        # the __get__ of function is id.
        if isinstance(class_variable, (AnalysisFunction, ArtificialFunction)):
            return_value.inject(class_variable)
        elif isinstance(class_variable, Typeshed):
            return_value.inject(class_variable)
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
            return_value.inject(class_variable)

    return_value.inject(class_variables)
    return_value = refine_value(return_value)

    return return_value


def type_getattro_Refined(type, name: str):

    class_variables = _pytype_lookup(type, name)
    if class_variables.is_any():
        return Value.make_any(), -1

    # step 1, descriptors
    return_value = Value()
    if len(class_variables):
        for class_variable in class_variables:
            # classmethod object
            if isinstance(class_variable, ClassmethodAnalysisInstance):
                functions = class_variable.tp_dict.read_value(
                    class_variable.tp_container
                )
                for function in functions:
                    if isinstance(function, AnalysisFunction):
                        one_res = AnalysisMethod(
                            tp_function=function, tp_instance=class_variable
                        )
                        return_value.inject(one_res)
                    else:
                        raise NotImplementedError
            # static method object
            elif isinstance(class_variable, StaticmethodAnalysisInstance):
                functions = class_variable.tp_dict.read_value(
                    class_variable.tp_container
                )
                for function in functions:
                    if isinstance(function, AnalysisFunction):
                        return_value.inject(function)
                    else:
                        raise NotImplementedError
            else:
                break
        else:
            if return_value.is_any():
                return Value.make_any(), -1
            elif len(return_value) > 0:
                return_value = refine_value(return_value)
                return return_value, 1

        if return_value.is_any():
            return Value.make_any(), -1
        elif len(return_value) > 0:
            return Value.make_any(), -1

    # step 2, non data descriptor
    return_value = Value()
    if len(class_variables):
        for class_variable in class_variables:
            # classmethod object
            if isinstance(
                class_variable,
                (ClassmethodAnalysisInstance, StaticmethodAnalysisInstance),
            ):
                break
            else:
                return_value = refine_value(return_value)
                return_value.inject(class_variable)
        else:
            if return_value.is_any():
                return Value.make_any(), -1
            elif len(return_value) > 0:
                return_value = refine_value(return_value)
                return return_value, 2

    return Value.make_any(), -1


def analysis_setattr(obj, name: str, value: Value | None) -> Value:
    if isinstance(obj, AnalysisInstance):
        return GenericSetAttr(obj, name, value)
    elif isinstance(obj, AnalysisClass):
        return type_setattro(obj, name, value)
    elif isinstance(obj, AnalysisFunction):
        return obj.tp_dict.write_local_value(name, value)
    # elif isinstance(obj, Typeshed):
    #     return result_value
    raise NotImplementedError(f"analysis_setattr ({obj},{name},{value})")


def GenericSetAttr(obj, name: str, value: Value | None):
    if sys.analysis_type == "crude":
        return GenericSetAttr_Crude(obj, name, value)
    elif sys.analysis_type == "refined":
        res, kind = GenericSetAttr_Refined(obj, name, value)
        if kind == -1:
            return GenericSetAttr_Crude(obj, name, value)
        else:
            return res
    else:
        raise NotImplementedError


def GenericSetAttr_Refined(obj, name: str, value: Value | None):
    if value is None:
        return GenericDelAttr_Uniform(obj, name)

    obj_type = _py_type(obj)
    # look up class dict
    class_variables = _pytype_lookup(obj_type, name)
    if class_variables.is_any():
        return Value().make_any(), -1

    # step 1, descriptors
    possible_descriptors = Value()
    if len(class_variables):
        for cls_var in class_variables:
            # check property instance
            if isinstance(cls_var, PropertyAnalysisInstance):
                # setattr
                fsets = cls_var.tp_dict.read_value(cls_var.tp_container[1])
                for fset in fsets:
                    if isinstance(fset, AnalysisFunction):
                        obj_value = type_2_value(obj)
                        value_value = value
                        one_value = AnalysisDescriptor(fset, obj_value, value_value)
                        possible_descriptors.inject(one_value)
                    elif fset is None_Instance:
                        pass
                    else:
                        raise NotImplementedError
            else:
                break
        else:
            # if they are all data descriptors
            if possible_descriptors.is_any():
                return Value.make_any(), -1
            elif len(possible_descriptors) > 0:
                return possible_descriptors, 1

    # check if it has both descriptor and normal
    if possible_descriptors.is_any():
        return Value.make_any(), -1
    elif len(possible_descriptors) > 0:
        return Value.make_any(), -1

    # step 2, set instance dict
    possible_descriptors = Value()
    # to keep sound, merge value
    obj.tp_dict.overwrite_local_value(name, value)
    return possible_descriptors, 2


def GenericSetAttr_Crude(obj, name: str, value: Value | None):
    # if value is None, the delete method is called
    if value is None:
        return GenericDelAttr_Uniform(obj, name)

    obj_type = _py_type(obj)
    # look up class dict
    class_variables = _pytype_lookup(obj_type, name)

    possible_descriptors = Value()
    for cls_var in class_variables:
        # check property instance
        if isinstance(cls_var, PropertyAnalysisInstance):
            # setattr
            fsets = cls_var.tp_dict.read_value(cls_var.tp_container[1])
            for fset in fsets:
                if isinstance(fset, AnalysisFunction):
                    obj_value = type_2_value(obj)
                    value_value = value
                    one_value = AnalysisDescriptor(fset, obj_value, value_value)
                    possible_descriptors.inject(one_value)

    # to keep sound, merge value
    obj.tp_dict.write_local_value(name, value)

    # return descriptors
    return possible_descriptors


def GenericDelAttr_Uniform(obj, name: str):
    # store possible descriptors
    obj_type = _py_type(obj)
    # look up class dict
    class_variables = _pytype_lookup(obj_type, name)

    possible_descriptors = Value()
    for cls_var in class_variables:
        # check property instance
        if isinstance(cls_var, PropertyAnalysisInstance):
            fdels = cls_var.tp_dict.read_value(cls_var.tp_container[2])
            for fdel in fdels:
                if isinstance(fdel, AnalysisFunction):
                    obj_value = type_2_value(obj)
                    one_value = AnalysisDescriptor(fdel, obj_value)
                    possible_descriptors.inject(one_value)
                elif fdel is None_Instance:
                    pass
                else:
                    raise NotImplementedError

    # return descriptors
    return possible_descriptors, 1


def type_delattro(type, name):
    return Value()


def type_setattro(type, name: str, value: Value | None):
    if value is None:
        return type_delattro(type, name)
    return GenericSetAttr(type, name, value)
