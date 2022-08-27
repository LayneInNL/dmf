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
from typing import Tuple

from dmf.analysis.all_types import (
    AnalysisInstance,
    AnalysisFunction,
    AnalysisModule,
    AnalysisMethod,
    evaluate,
    AnalysisDescriptorGetFunction,
    None_Instance,
    AnalysisDescriptorSetFunction,
)
from dmf.analysis.artificial_types import (
    ArtificialClass,
    ArtificialFunction,
    ArtificialMethod,
)
from dmf.analysis.special_types import Bases_Any
from dmf.analysis.typeshed_types import TypeshedModule, TypeshedFunction
from dmf.analysis.value import Value, type_2_value


def _py_type(obj):
    return obj.tp_class


def _pytype_lookup(obj_type, name) -> Value:
    res = _find_name_in_mro(obj_type, name)
    return res


def _pytype_lookup_by_obj(obj, name) -> Value:
    obj_type = _py_type(obj)

    value = Value()
    for obj_type in obj_type:
        _value = _pytype_lookup(obj_type, name)
        value.inject(_value)

    return value


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


def _find_name_in_mro(obj_type, name) -> Value:
    all_mro_value = Value()
    tp_mros = obj_type.tp_mro
    for tp_mro in tp_mros:
        for cls in tp_mro:
            if cls is Bases_Any:
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


def _getattr(obj, name) -> Tuple[Value, Value]:

    obj_type = _py_type(obj)
    # get the __getattribute__ of this obj
    tp_getattributes = _pytype_lookup(obj_type, "__getattribute__")
    if len(tp_getattributes) == 0:
        if isinstance(obj, AnalysisInstance):
            return GenericGetAttr(obj, name)
        elif isinstance(obj, ArtificialClass):
            return type_getattro(obj, name)
        # work on class
        if isinstance(obj, AnalysisFunction):
            return GenericGetAttr(obj, name)
        elif isinstance(obj, AnalysisModule):
            try:
                res = obj.getattr(name)
            except AttributeError:
                return Value(), Value()
            else:
                return res, Value()
        elif isinstance(obj, TypeshedModule):
            try:
                res = obj.getattr(name)
            except AttributeError:
                return Value(), Value()
            else:
                direct_res, descr_gets = Value(), Value()
                direct_res.inject(res)
                return direct_res, descr_gets
        else:
            raise NotImplementedError
    else:
        return Value.make_any(), Value.make_any()


def GenericGetAttr(obj, name):
    # two preset return values
    res_value, descr_value = Value(), Value()

    # get types of obj
    obj_type = _py_type(obj)

    # try finding descriptors
    descrs = _pytype_lookup(obj_type, name)
    if descrs.is_Any():
        return Value.make_any(), Value.make_any()

    # traverse descrs
    for descr in descrs:
        if isinstance(descr, AnalysisFunction):
            one_descr = AnalysisMethod(tp_function=descr, tp_instance=obj)
            descr_value.inject(one_descr)
        elif isinstance(descr, ArtificialFunction):
            one_descr = ArtificialMethod(tp_function=descr, tp_instance=obj)
            descr_value.inject(one_descr)
        else:
            # types of descriptor
            descr_types = _py_type(descr)
            if descr_types.is_Any():
                return Value.make_any(), Value.make_any()

            for descr_type in descr_types:
                descr_tp_gets = _pytype_lookup(descr_type, "__get__")
                if descr_tp_gets.is_Any():
                    return Value.make_any(), Value.make_any()

                for descr_tp_get in descr_tp_gets:
                    # descr_tp_get must be AnalysisFunction
                    if isinstance(descr_tp_get, AnalysisFunction):
                        # self = descr, obj = obj, type=tp
                        one_descr = AnalysisDescriptorGetFunction(
                            tp_self=descr,
                            tp_obj=type_2_value(obj),
                            tp_objtype=obj_type,
                        )
                        descr_value.inject(one_descr)
                    else:
                        raise NotImplementedError

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
            typeshed_value = evaluate(descr)
            res_value.inject(typeshed_value)
        else:
            descriptor_types = _py_type(descr)
            if descriptor_types.is_Any():
                return Value.make_any(), Value.make_any()

            for descriptor_type in descriptor_types:
                descriptor_type_gets = _pytype_lookup(descriptor_type, "__get__")
                if descriptor_type_gets.is_Any():
                    return Value.make_any(), Value.make_any()

                for descriptor_type_get in descriptor_type_gets:
                    if isinstance(descriptor_type_get, AnalysisFunction):
                        one_descr = AnalysisDescriptorGetFunction(
                            tp_self=descr,
                            tp_obj=type_2_value(None_Instance),
                            tp_objtype=type_2_value(type),
                        )
                        descr_value.inject(one_descr)
                    else:
                        raise NotImplementedError

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
