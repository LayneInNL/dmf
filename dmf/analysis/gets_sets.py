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
    AnalysisDescriptorGetFunction,
    None_Instance,
    AnalysisDescriptorSetFunction,
    AnalysisClass,
    refine_value,
    Constructor,
    PropertyArtificialClass,
    AnalysisPropertyGetFunction,
    ClassmethodArtificialClass,
    AnalysisClassmethodMethod,
    StaticmethodArtificialClass,
    Super_Type,
    SuperArtificialClass,
)
from dmf.analysis.artificial_types import (
    ArtificialClass,
    ArtificialFunction,
    ArtificialMethod,
)
from dmf.analysis.special_types import Bases_Any, MRO_Any
from dmf.analysis.typeshed_types import TypeshedModule, TypeshedFunction
from dmf.analysis.value import Value, type_2_value


def _py_type(obj):
    return obj.tp_class


def _pytype_lookup(obj_type, name, mros=None) -> Value:
    res = _find_name_in_mro(obj_type, name, mros)
    return res


def _pytype_lookup_set(type, name, value):
    res = _find_name_in_mro(type, name)
    if res.is_Any():
        return Value.make_any()

    # no class variable called name
    if len(res) == 0:
        type.tp_dict.write_local_value(name, value)
        return type.tp_dict.read_value(name)
    # class variable exists, return this one
    else:
        res.inject_value(value)
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
    # tp_setattr = _pytype_lookup(tp, "__setattr__")
    # if len(tp_setattr) == 0:
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

    obj_type = _py_type(obj)
    # get the __getattribute__ of this obj
    # tp_getattributes = _pytype_lookup(obj_type, "__getattribute__")
    # if len(tp_getattributes) == 0:
    if isinstance(obj, AnalysisInstance):
        return GenericGetAttr(obj, name)
    elif isinstance(obj, AnalysisClass):
        return type_getattro(obj, name)
    elif isinstance(obj, ArtificialClass):
        return type_getattro(obj, name)
    # work on class
    elif isinstance(obj, AnalysisFunction):
        return GenericGetAttr(obj, name)
    elif isinstance(obj, (AnalysisModule, TypeshedModule)):
        direct_res, descr_gets = Value(), Value()
        try:
            res = obj.getattr(name)
            res = refine_value(res)
        except AttributeError:
            return direct_res, descr_gets
        else:
            direct_res.inject(res)
            return res, descr_gets
    elif isinstance(obj, TypeshedModule):
        direct_res, descr_gets = Value(), Value()
        try:
            res = obj.getattr(name)
        except AttributeError:
            return direct_res, descr_gets
        else:
            direct_res.inject(res)
            return direct_res, descr_gets
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
    descrs = _pytype_lookup(obj_type, name, mros)
    if descrs.is_Any():
        return Value.make_any(), Value.make_any()

    # traverse descrs
    for descr in descrs:
        # if descr is a function, there is an implicit __set__
        if isinstance(descr, AnalysisFunction):
            one_descr = AnalysisMethod(tp_function=descr, tp_instance=obj)
            descr_value.inject(one_descr)
        # if descr is a function, there is an implicit __set__
        elif isinstance(descr, ArtificialFunction):
            one_descr = ArtificialMethod(tp_function=descr, tp_instance=obj)
            descr_value.inject(one_descr)
        else:
            descr_type = _py_type(descr)
            if isinstance(descr_type, PropertyArtificialClass):
                fgets = sys.heap.read_field_from_address(descr.tp_address, "fget")
                if fgets.is_Any():
                    return Value.make_any(), Value.make_any()
                for fget in fgets:
                    if isinstance(fget, AnalysisFunction):
                        one_descr = AnalysisPropertyGetFunction(obj, fget)
                        descr_value.inject(one_descr)
                    else:
                        raise NotImplementedError(fget)
            elif isinstance(descr_type, ClassmethodArtificialClass):
                functions = sys.heap.read_field_from_address(
                    descr.tp_address, "function"
                )
                if functions.is_Any():
                    return Value.make_any(), Value.make_any()
                for function in functions:
                    if isinstance(function, AnalysisFunction):
                        one_res = AnalysisClassmethodMethod(
                            tp_function=function, tp_instance=obj_type
                        )
                        res_value.inject(one_res)
                    else:
                        raise NotImplementedError(function)
            elif isinstance(descr_type, StaticmethodArtificialClass):
                functions = sys.heap.read_field_from_address(
                    descr.tp_address, "function"
                )
                if functions.is_Any():
                    return Value.make_any(), Value.make_any()
                for function in functions:
                    if isinstance(function, AnalysisFunction):
                        res_value.inject(function)
                    else:
                        raise NotImplementedError(function)

            else:
                descr_tp_gets = _pytype_lookup(descr_type, "__get__")
                if descr_tp_gets.is_Any():
                    return Value.make_any(), Value.make_any()

                for descr_tp_get in descr_tp_gets:
                    # descr_tp_get must be AnalysisFunction
                    if isinstance(descr_tp_get, AnalysisFunction):
                        # self = descr, obj = obj, type=tp
                        one_descr = AnalysisDescriptorGetFunction(
                            tp_self=descr,
                            tp_obj=obj,
                            tp_objtype=obj_type,
                            tp_function=descr_tp_get,
                        )
                        descr_value.inject(one_descr)
                    else:
                        raise NotImplementedError(f"{obj},{name}")

    tp_dict = obj.tp_dict
    if name in obj.tp_dict:
        one_res = tp_dict.read_value(name)
        res_value.inject(one_res)

    res_value.inject(descrs)

    return res_value, descr_value


def type_getattro(type, name) -> Tuple[Value, Value]:
    res_value, descr_value = Value(), Value()

    descrs = _pytype_lookup(type, name)
    if descrs.is_Any():
        return Value.make_any(), Value.make_any()

    for descr in descrs:
        # the __get__ of function is id.
        if isinstance(descr, (AnalysisFunction, ArtificialFunction)):
            res_value.inject(descr)
        elif isinstance(descr, TypeshedFunction):
            typeshed_value = refine_type(descr)
            res_value.inject(typeshed_value)
        elif isinstance(descr, Constructor):
            res_value.inject(descr)
        else:
            descriptor_type = _py_type(descr)

            descriptor_type_gets = _pytype_lookup(descriptor_type, "__get__")
            if descriptor_type_gets.is_Any():
                return Value.make_any(), Value.make_any()

            for descriptor_type_get in descriptor_type_gets:
                if isinstance(descriptor_type_get, AnalysisFunction):
                    one_descr = AnalysisDescriptorGetFunction(
                        tp_self=descr,
                        tp_obj=None_Instance,
                        tp_objtype=type,
                        tp_function=descriptor_type,
                    )
                    descr_value.inject(one_descr)
                else:
                    raise NotImplementedError(f"{type},{name}")

    if name in type.tp_dict:
        one_res = type.tp_dict.read_value(name)
        res_value.inject_value(one_res)

    if descrs is not None:
        res_value.inject_value(descrs)

    return res_value, descr_value


def GenericSetAttr(obj, name, value):
    descr_value = Value()

    obj_types = _py_type(obj)
    if obj_types.is_Any():
        return Value.make_any()

    # look up class dict
    for obj_type in obj_types:
        descriptors = _pytype_lookup_set(obj_type, name, value)
        if descriptors.is_Any():
            return Value.make_any()

        for descriptor in descriptors:
            descriptor_types = _py_type(descriptor)
            if descriptor_types.is_Any():
                return Value.make_any()

            for descriptor_type in descriptor_types:
                descriptor_type_sets = _pytype_lookup(descriptor_type, "__set__")
                if descriptor_type_sets.is_Any():
                    return Value.make_any()

                for descriptor_type_set in descriptor_type_sets:
                    if isinstance(descriptor_type_set, AnalysisFunction):
                        one_descr = AnalysisDescriptorSetFunction(
                            tp_self=descriptor_type,
                            tp_obj=type_2_value(obj),
                            tp_value=value,
                        )
                        descr_value.inject(one_descr)
                    else:
                        raise NotImplementedError(descriptor_type_set)

    # instance dict assignment
    obj.tp_dict.write_local_value(name, value)

    return descr_value


def type_setattro(type, name, value):
    return GenericSetAttr(type, name, value)
