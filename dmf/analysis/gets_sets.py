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
    refine_type,
    None_Instance,
    AnalysisClass,
    refine_value,
    Constructor,
    SuperArtificialClass,
    AnalysisDescriptor,
    AnalysisDescriptor,
    ClassmethodAnalysisInstance,
    PropertyAnalysisInstance,
    StaticmethodAnalysisInstance,
    TypeExprVisitor,
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
            else:
                # tp_dict could belong to AnalysisClass, ArtificialClass and
                # TypeshedClass
                if name not in cls.tp_dict:
                    if hasattr(cls, "tp_fallback"):
                        fallback_clses = cls.tp_fallback
                        assert len(fallback_clses) == 1
                        fallback_cls = fallback_clses.value_2_list()[0]
                        if name in fallback_cls.tp_dict:
                            curr_mro_value = fallback_cls.tp_dict.read_value(name)
                            all_mro_value.inject(curr_mro_value)
                            break

                else:
                    curr_mro_value = cls.tp_dict.read_value(name)
                    all_mro_value.inject(curr_mro_value)
                    break

    return all_mro_value


# simulate builtins.getattr, but operate on a set of objects
def getattrs(objs: Value, name: str, default=None) -> Tuple[Value, Value]:
    # if objs is Any, just return two Anys
    if objs.is_Any():
        return Value(any=True), Value(any=True)

    # direct results
    direct_res = Value()
    # possible descriptor getters
    descr_gets = Value()

    for obj in objs:
        curr_direct_res, curr_descr_gets = _getattr(obj, name)
        direct_res += curr_direct_res
        descr_gets += curr_descr_gets

    # add default to direct_res
    if default is not None:
        direct_res.inject(default)

    return direct_res, descr_gets


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
    raise NotImplementedError(f"setattr({obj},{name},{value})")
    # # work on class
    # if isinstance(obj, ClassLevel):
    #     return type_setattro(obj, name, value)
    # elif isinstance(obj, Instance):
    #     return GenericSetAttr(obj, name, value)
    # elif isinstance(obj, AnalysisFunction):
    #     return GenericSetAttr(obj, name, value)
    # else:
    #     raise NotImplementedError(f"setattr({obj},{name},{value})")
    # else:
    #     return Value(any=True)

    return value


def _getattr(obj, name) -> Tuple[Value, Value]:

    # get the __getattribute__ of this obj
    # tp_getattributes = _pytype_lookup(obj_type, "__getattribute__")
    # if len(tp_getattributes) == 0:
    if isinstance(obj, AnalysisInstance):
        return GenericGetAttr(obj, name)
    elif isinstance(obj, TypeshedInstance):
        return GenericGetAttr(obj, name)
    elif isinstance(obj, AnalysisClass):
        return type_getattro(obj, name)
    elif isinstance(obj, ArtificialClass):
        return type_getattro(obj, name)
    # work on class
    elif isinstance(obj, AnalysisFunction):
        return GenericGetAttr(obj, name)
    elif isinstance(obj, (AnalysisModule, TypeshedModule)):
        direct_result, descriptor_result = Value(), Value()
        if name in obj.tp_dict:
            instance_value = obj.tp_dict.read_value(name)
            direct_result.inject(instance_value)
            direct_result = refine_value(direct_result)
        else:
            raise NotImplementedError(name)
        return direct_result, descriptor_result
    elif isinstance(obj, TypeshedClass):
        return type_getattro(obj, name)
    else:
        raise NotImplementedError(obj)
    # else:
    #     return Value.make_any(), Value.make_any()


def GenericGetAttr(obj, name):
    # two preset return values
    res_value, descr_value = Value(), Value()

    # get types of obj
    obj_type = _py_type(obj)
    mros = None
    if isinstance(obj_type, SuperArtificialClass):
        # super is so complicated
        tp_dict = sys.heap.read_instance_dict(obj.tp_address)
        obj = getattr(tp_dict, "super_self")
        obj_type = _py_type(obj)
        mros = getattr(tp_dict, "super_mros")

    # try finding descriptors
    class_variables = _pytype_lookup(obj_type, name, mros)

    # traverse descrs
    for class_variable in class_variables:
        # if descr is a function, there is an implicit __set__
        if isinstance(class_variable, AnalysisFunction):
            one_value = AnalysisMethod(tp_function=class_variable, tp_instance=obj)
            res_value.inject(one_value)
        # if descr is a function, there is an implicit __set__
        elif isinstance(class_variable, ArtificialFunction):
            one_value = ArtificialMethod(tp_function=class_variable, tp_instance=obj)
            res_value.inject(one_value)
        # if descr is a typeshed, we already know its information.
        # So we have to translate it into abstract value
        # @property def test(): int, in this case we extract int
        # def test(): int, in this case we extract test function
        elif isinstance(class_variable, Typeshed):
            res_value.inject(class_variable)
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
                    descr_value.inject(one_value)
            elif isinstance(class_variable, ClassmethodAnalysisInstance):
                functions = class_variable.tp_dict.read_value(
                    class_variable.tp_container
                )
                for function in functions:
                    one_res = AnalysisMethod(tp_function=function, tp_instance=obj_type)
                    res_value.inject(one_res)
            elif isinstance(class_variable, StaticmethodAnalysisInstance):
                functions = class_variable.tp_dict.read_value(
                    class_variable.tp_container
                )
                for function in functions:
                    res_value.inject(function)
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
                        descr_value.inject(one_value)
                    else:
                        raise NotImplementedError(f"{obj},{name}")

    tp_dict = obj.tp_dict
    if name in obj.tp_dict:
        one_res = tp_dict.read_value(name)
        res_value.inject(one_res)

    res_value.inject(class_variables)

    res_value = refine_value(res_value)

    return res_value, descr_value


def type_getattro(type, name) -> Tuple[Value, Value]:
    res_value, descr_value = Value(), Value()

    class_variables = _pytype_lookup(type, name)
    for class_variable in class_variables:
        # the __get__ of function is id.
        if isinstance(class_variable, (AnalysisFunction, ArtificialFunction)):
            res_value.inject(class_variable)
        elif isinstance(class_variable, Typeshed):
            curr_visitor = TypeExprVisitor(class_variable)
            curr_value = curr_visitor.refine()
            res_value.inject(curr_value)
        elif isinstance(class_variable, Constructor):
            res_value.inject(class_variable)
        # property object itself
        elif isinstance(class_variable, PropertyAnalysisInstance):
            res_value.inject(class_variable)
        # classmethod object
        elif isinstance(class_variable, ClassmethodAnalysisInstance):
            functions = class_variable.tp_dict.read_value(class_variable.tp_container)
            for function in functions:
                one_res = AnalysisMethod(
                    tp_function=function, tp_instance=class_variable
                )
                res_value.inject(one_res)
        # static method object
        elif isinstance(class_variable, StaticmethodAnalysisInstance):
            functions = class_variable.tp_dict.read_value(class_variable.tp_container)
            for function in functions:
                res_value.inject(function)
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
                    descr_value.inject(one_descr)
                else:
                    raise NotImplementedError(f"{type},{name}")

    if name in type.tp_dict:
        one_res = type.tp_dict.read_value(name)
        res_value.inject(one_res)

    res_value.inject(class_variables)

    return res_value, descr_value


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
