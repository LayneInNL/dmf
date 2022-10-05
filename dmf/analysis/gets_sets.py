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
def getattrs(objs: Value, name: str) -> Value:
    direct_res = Value()
    for obj in objs:
        curr_direct_res = analysis_getattr(obj, name)
        direct_res += curr_direct_res

    return direct_res


def analysis_getattr(obj, name) -> Value:
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


def setattrs(objs, name, value) -> Value:
    descr_sets = Value()
    for obj in objs:
        curr_descr_sets = analysis_setattr(obj, name, value)
        descr_sets += curr_descr_sets

    return descr_sets


def analysis_setattr(obj, name, value) -> Value:
    result_value = Value()
    if obj is Any:
        return result_value
    elif isinstance(obj, AnalysisInstance):
        return GenericSetAttr(obj, name, value)
    elif isinstance(obj, AnalysisClass):
        return type_setattro(obj, name, value)
    elif isinstance(obj, AnalysisFunction):
        return GenericSetAttr(obj, name, value)
    elif isinstance(obj, Typeshed):
        return result_value
    raise NotImplementedError(f"setattr({obj},{name},{value})")


def GenericGetAttr(obj, name):
    return_value = Value()

    # get types of obj
    obj_type = _py_type(obj)

    # deal with super()
    # super is like a proxy object
    mros = None
    if isinstance(obj, SuperAnalysisInstance):
        obj = obj.tp_self
        mros = obj.tp_mro
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
            # go through normal cases
            cls_var_type = _py_type(cls_var)
            # normal __get__ lookup, only AnalysisClass is considered
            if not isinstance(cls_var_type, AnalysisClass):
                logger.info(f"{cls_var_type} is not an AnalysisClass")
                continue

            cls_var_type_gets = _pytype_lookup(cls_var_type, "__get__")
            for cls_var_type_get in cls_var_type_gets:
                # descr_tp_get must be AnalysisFunction
                # descr.__get__(self, obj, type=None) -> value
                if isinstance(cls_var_type_get, AnalysisFunction):
                    descr_value = type_2_value(cls_var)
                    obj_value = type_2_value(obj)
                    obj_type_value = type_2_value(obj_type)
                    one_value = AnalysisDescriptor(
                        cls_var_type_get,
                        descr_value,
                        obj_value,
                        obj_type_value,
                    )
                    return_value.inject(one_value)
                else:
                    raise NotImplementedError(f"{obj},{name}")

    if name in obj.tp_dict:
        one_res = obj.tp_dict.read_value(name)
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

    if type.tp_dict.contains(name):
        one_res = type.tp_dict.read_value(name)
        return_value.inject(one_res)

    return_value.inject(class_variables)

    return_value = refine_value(return_value)

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
                    receiver_value = type_2_value(class_variable)
                    obj_value = type_2_value(obj)
                    one_descr = AnalysisDescriptor(
                        descriptor_type_del, receiver_value, obj_value
                    )
                    descr_value.inject(one_descr)
                else:
                    raise NotImplementedError(descriptor_type_del)

    return descr_value


def GenericSetAttr(obj, name, value):
    # if value is None, the delete method is called
    if value is None:
        return GenericDelAttr(obj, name)

    # store possible descriptors
    possible_descriptors = Value()

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
                possible_descriptors.inject(one_value)
        else:
            class_variable_type = _py_type(class_variable)
            if not isinstance(class_variable_type, AnalysisClass):
                logger.info(f"{class_variable_type} is not analysis class")
                continue

            # check if there is a __set__
            descriptor_type_dels = _pytype_lookup(class_variable_type, "__set__")
            for descriptor_type_del in descriptor_type_dels:
                if isinstance(descriptor_type_del, AnalysisFunction):
                    descriptor_receiver = type_2_value(class_variable)
                    obj_value = type_2_value(obj)
                    value_value = value
                    one_descr = AnalysisDescriptor(
                        descriptor_type_del, descriptor_receiver, obj_value, value_value
                    )
                    possible_descriptors.inject(one_descr)
                else:
                    raise NotImplementedError(descriptor_type_del)

    # to keep sound, merge value
    obj.tp_dict.write_local_value(name, value)

    # return descriptors
    return possible_descriptors


def type_delattro(type, name):
    pass


def type_setattro(type, name, value):
    return GenericSetAttr(type, name, value)
