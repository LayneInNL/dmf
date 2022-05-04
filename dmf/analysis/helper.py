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
import ast
import logging
from typing import List, Dict

from dmf.analysis.lattice import Lattice
from dmf.analysis.state import State
from dmf.analysis.value import (
    Value,
    NUM_TYPE,
    NONE_TYPE,
    BOOL_TYPE,
    STR_TYPE,
    BYTE_TYPE,
)


def is_func_type(value: Value):
    func_type = value.extract_func_type()
    class_type = value.extract_class_type()
    if func_type and not class_type:
        return True
    return False


def is_class_type(value: Value):
    func_type = value.extract_func_type()
    class_type = value.extract_class_type()
    if not func_type and class_type:
        return True
    return False


def get_func_or_class_label(name: str, lattice: Lattice):
    values: List[State] = list(lattice.values())
    state: State = values[0]
    value: Value = state.read_var_from_stack(name)
    logging.debug("Value is {}".format(value))
    func_labels = list(value.extract_func_type())
    if not func_labels:
        class_label_value = value.extract_class_type()
        frame: Dict[str, Value] = class_label_value
        func_value: Value = frame["__init__"]
        func_labels = list(func_value.extract_func_type())
    return func_labels[0]


def get_callable_name(expr: ast.expr):
    assert isinstance(expr, ast.Call)
    if isinstance(expr.func, ast.Name):
        return expr.func.id
    else:
        assert False


def record(label, context):
    return label


def merge(label, heap, context):
    return context[-1:] + (label,)


def get_value(expr: ast.expr, state: State):
    if isinstance(expr, ast.Num):
        value = Value()
        value.inject_prim_type(NUM_TYPE)
        return value
    elif isinstance(expr, ast.NameConstant):
        value = Value()
        if expr.value is None:
            value.inject_prim_type(NONE_TYPE)
        else:
            value.inject_prim_type(BOOL_TYPE)
        return value
    elif isinstance(expr, (ast.Str, ast.JoinedStr)):
        value = Value()
        value.inject_prim_type(STR_TYPE)
        return value
    elif isinstance(expr, ast.Bytes):
        value = Value()
        value.inject_prim_type(BYTE_TYPE)
    elif isinstance(expr, ast.Name):
        return state.read_var_from_stack(expr.id)
    elif isinstance(expr, ast.Attribute):
        attr = expr.attr
        assert isinstance(expr.value, ast.Name)
        name = expr.value.id
        value = state.read_var_from_stack(name)
        heaps = list(value.extract_heap_type())
        assert len(heaps) == 1
        if state.heap_contains(heaps[0], attr):
            return state.read_field_from_heap(heaps[0], attr)
        else:
            # look it up in class objects
            pass
    else:
        assert False
