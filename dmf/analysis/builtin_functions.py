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
    AnalysisFunction,
    AnalysisMethod,
    Bool_Instance,
    Str_Instance,
    ByteArray_Instance,
    Bytes_Instance,
    AnalysisInstance,
    Int_Instance,
    Float_Instance,
    None_Instance,
)
from dmf.analysis.artificial_basic_types import (
    ArtificialFunction,
    ArtificialMethod,
)
from dmf.analysis.gets_sets import getattrs
from dmf.analysis.namespace import Namespace
from dmf.analysis.typeshed_types import (
    parse_typeshed_module,
    extract_1value,
    import_a_module_from_typeshed,
)
from dmf.analysis.value import Value, type_2_value
from dmf.importer import import_module

# since we use static analysis, builtin_module is a set of modules
# but in fact there will only be one module
builtin_modules: Value = parse_typeshed_module("builtins")
builtin_module = extract_1value(builtin_modules)
builtin_module_dict: Namespace = builtin_module.tp_dict


def _setup_abs():
    def abs(x):
        return type_2_value(Int_Instance)


def _setup_all():
    def all(iterable):
        return type_2_value(Bool_Instance)


def _setup_any():
    def any(iterable):
        return type_2_value(Bool_Instance)


def _setup_ascii(object):
    def ascii(iterable):
        return type_2_value(Str_Instance)


def _setup_bin():
    def bin(x):
        return type_2_value(Str_Instance)


def _setup_bool():
    def bool(x=None):
        return type_2_value(Bool_Instance)


def _setup_bytearray():
    def bytearray(source=None, encoding=None, errors=None):
        return type_2_value(ByteArray_Instance)


def _setup_bytes():
    def bytes(source=None, encoding=None, errors=None):
        return type_2_value(Bytes_Instance)


def _setup_callable():
    def callable(object):
        return type_2_value(Bool_Instance)


def _setup_chr():
    def chr(i):
        return type_2_value(Str_Instance)


# classmethod is in another file


def _setup_compile():
    def compile(source, filename, mode, flags=0, dont_inherit=False, optimize=-1):
        return Value.make_any()


def _setup_eval():
    def eval(expression, globals=None, locals=None):
        return Value.make_any()


def _setup_exec():
    def exec(object, globals=None, locals=None):
        return Value.make_any()


def _setup_float():
    def float(x=None):
        return type_2_value(Float_Instance)


def _setup_format():
    def format(value, format_spec=None):
        return type_2_value(Str_Instance)


def _setup_hash():
    def hash(object):
        return type_2_value(Int_Instance)


def _setup_hex():
    def hex(x):
        return type_2_value(Str_Instance)


def _setup_id():
    def id(object):
        return type_2_value(Int_Instance)


def _setup_input():
    def input(prompt=None):
        return type_2_value(Str_Instance)


def _setup_int():
    def int(x=None, base=None):
        return type_2_value(Int_Instance)


def _setup_isinstance():
    def isinstance(object, classinfo):
        return type_2_value(Bool_Instance)


def _setup_issubclass():
    def isinstance(cls, classinfo):
        return type_2_value(Bool_Instance)


def _setup_len():
    def len(s):
        return type_2_value(Int_Instance)


def _setup_max():
    def max(*args, **kwargs):
        return type_2_value(Int_Instance)


def _setup_min():
    def min(*args, **kwargs):
        return type_2_value(Int_Instance)


def _setup_oct():
    def oct(x):
        return type_2_value(Str_Instance)


def _setup_ord():
    def ord(c):
        return type_2_value(Int_Instance)


def _setup_pow():
    def pow(base, exp=None, mod=None):
        return type_2_value(Int_Instance)


def _setup_print():
    def print(*args, **kwargs):
        return type_2_value(None_Instance)


def _setup_repr():
    def repr(object):
        return type_2_value(Str_Instance)


def _setup_round():
    def round(*args, **kwargs):
        return type_2_value(Int_Instance)


def _setup_str():
    def str(*args, **kwargs):
        return type_2_value(Str_Instance)


def _setup_sum():
    def sum(*args, **kwargs):
        return type_2_value(Int_Instance)


# complex no occurrence


def _setup_builtin_types():
    # mimic builtins.iter
    def iter(objs, sentinel=None):
        if objs.is_Any():
            return Value.make_any()

        if sentinel is not None:
            return Value.make_any()

        value = Value()

        direct_res, descr_res = getattrs(objs, "__iter__")
        if direct_res.is_Any() or descr_res.is_Any():
            return Value.make_any()

        for one_direct_res in direct_res:
            if isinstance(one_direct_res, ArtificialFunction):
                res = one_direct_res(objs)
                value.inject(res)
            elif isinstance(one_direct_res, AnalysisFunction):
                value.inject(one_direct_res)
            else:
                raise NotImplementedError

        for one_descr_res in descr_res:
            if isinstance(one_descr_res, ArtificialMethod):
                pass
                # res = one_descr_res(objs)
                # value.inject(res)
            elif isinstance(one_descr_res, AnalysisMethod):
                value.inject(one_descr_res)
            else:
                raise NotImplementedError(one_descr_res)

        return value

    arti_iter = ArtificialFunction(tp_function=iter, tp_qualname="builtins.iter")
    builtin_module_dict.write_local_value("iter", type_2_value(arti_iter))

    def next(objs, default=None):
        if objs.is_Any():
            return Value.make_any()

        value = Value()
        direct_res, descr_res = getattrs(objs, "__next__")
        if direct_res.is_Any() or descr_res.is_Any():
            return Value.make_any()

        for one_direct_res in direct_res:
            if isinstance(one_direct_res, ArtificialFunction):
                res = one_direct_res(objs)
                value.inject(res)
            elif isinstance(one_direct_res, AnalysisFunction):
                value.inject(one_direct_res)
            else:
                raise NotImplementedError

        for one_descr_res in descr_res:
            if isinstance(one_descr_res, ArtificialMethod):
                pass
                # res = one_descr_res(objs)
                # value.inject(res)
            elif isinstance(one_descr_res, AnalysisMethod):
                value.inject(one_descr_res)
            else:
                raise NotImplementedError(one_descr_res)

        if default is not None:
            return value.inject(default)
        return value

    arti_next = ArtificialFunction(tp_function=next, tp_qualname="builtins.next")
    builtin_module_dict.write_local_value("next", type_2_value(arti_next))


_setup_builtin_types()


def _resolve_name(name, package, level):
    """Resolve a relative module name to an absolute one."""
    bits = package.rsplit(".", level - 1)
    if len(bits) < level:
        raise ValueError("attempted relative import beyond top-level package")
    base = bits[0]
    return "{}.{}".format(base, name) if name else base


def import_a_module(name, package=None, level=0) -> Value:
    import isort

    # package is needed
    if level > 0:
        name = _resolve_name(name, package, level)
    category = isort.place_module(name)

    if category == "STDLIB":
        module = import_a_module_from_typeshed(name)
    else:
        module = import_module(name)

    value = Value()
    value.inject(module)
    return value
