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
import builtins
import sys
from types import FunctionType

from dmf.analysis.analysis_types import (
    AnalysisFunction,
    None_Instance,
    Dict_Instance,
    AnalysisDescriptor,
    Str_Type,
    Int_Type,
    Bool_Type,
    ByteArray_Type,
    Bytes_Type,
    Float_Type,
    List_Instance,
    artificial_namespace,
)
from dmf.analysis.artificial_basic_types import (
    ArtificialFunction,
)
from dmf.analysis.gets_sets import analysis_getattr
from dmf.analysis.special_types import Any
from dmf.analysis.typeshed_types import (
    import_a_module_from_typeshed,
    TypeshedFunction,
)
from dmf.analysis.value import Value, type_2_value
from dmf.importer import import_module


def _setup():
    def abs(x):
        return type_2_value(Int_Type())

    def all(iterable):
        return type_2_value(Bool_Type())

    def any(iterable):
        return type_2_value(Bool_Type())

    def ascii(iterable):
        return type_2_value(Str_Type())

    def bin(x):
        return type_2_value(Str_Type())

    def bool(x=None):
        return type_2_value(Bool_Type())

    def bytearray(source=None, encoding=None, errors=None):
        return type_2_value(ByteArray_Type())

    def bytes(source=None, encoding=None, errors=None):
        return type_2_value(Bytes_Type())

    def callable(object):
        return type_2_value(Bool_Type())

    def chr(i):
        return type_2_value(Str_Type())

    def compile(source, filename, mode, flags=0, dont_inherit=False, optimize=-1):
        return Value.make_any()

    # classmethod is in another file

    def delattr(object, name):
        return Value.make_any()

    def divmod(*args, **kwargs):
        return Value.make_any()

    # dict is in another file

    def dir(object=None):
        value = type_2_value(List_Instance)
        return value

    def enumerate(iterable, start=None):
        return Value.make_any()

    def eval(expression, globals=None, locals=None):
        return Value.make_any()

    def exec(object, globals=None, locals=None):
        return Value.make_any()

    def filter(*args, **kwargs):
        return Value.make_any()

    def float(x=None):
        return type_2_value(Float_Type)

    def format(value, format_spec=None):
        return type_2_value(Str_Type())

    # frozenset is in another file

    def getattr(object, name, default=None):
        return Value.make_any()

    def globals():
        value = Value()
        value.inject(Dict_Instance)
        return value

    def hasattr(object, name):
        return type_2_value(Bool_Type())

    def hash(object):
        return type_2_value(Int_Type())

    def hex(x):
        return type_2_value(Str_Type())

    def id(object):
        return type_2_value(Int_Type())

    def input(prompt=None):
        return type_2_value(Str_Type())

    def int(x=None, base=None):
        return type_2_value(Int_Type())

    def isinstance(object, classinfo):
        return type_2_value(Bool_Type())

    def issubclass(cls, classinfo):
        return type_2_value(Bool_Type())

    def iter(objs, sentinel=None):
        if sentinel is not None:
            return Value.make_any()

        value = Value()
        for obj in objs:
            obj_type = obj.tp_class
            direct_res = analysis_getattr(obj_type, "__iter__")
            for one_direct_res in direct_res:
                if one_direct_res is Any:
                    value.inject(Any)
                elif builtins.isinstance(one_direct_res, ArtificialFunction):
                    one_res = one_direct_res(objs)
                    value.inject(one_res)
                elif builtins.isinstance(one_direct_res, AnalysisFunction):
                    one_res = AnalysisDescriptor(one_direct_res, type_2_value(obj))
                    value.inject(one_res)
                elif builtins.isinstance(one_direct_res, TypeshedFunction):
                    one_res = one_direct_res.refine_self_to_value()
                    value.inject(one_res)
        return value

    def len(s):
        return type_2_value(Int_Type())

    # list is in another file

    def locals():
        value = Value()
        value.inject(Dict_Instance)
        return value

    def map(*args, **kwargs):
        return Value.make_any()

    def max(*args, **kwargs):
        return type_2_value(Int_Type())

    def min(*args, **kwargs):
        return type_2_value(Int_Type())

    def next(objs, default=None):
        value = Value()
        for obj in objs:
            direct_res = analysis_getattr(obj, "__next__")
            for one_direct_res in direct_res:
                if one_direct_res is Any:
                    value.inject(Any)
                elif builtins.isinstance(one_direct_res, ArtificialFunction):
                    one_res = one_direct_res(type_2_value(obj))
                    value.inject(one_res)
                elif builtins.isinstance(one_direct_res, AnalysisFunction):
                    descriptor = AnalysisDescriptor(
                        tp_function=one_direct_res
                    ), type_2_value(obj)
                    value.inject(descriptor)
                elif builtins.isinstance(one_direct_res, TypeshedFunction):
                    one_res = one_direct_res.refine_self_to_value()
                    value.inject(one_res)

        if default is not None:
            return value.inject(default)
        return value

    def oct(x):
        return type_2_value(Str_Type())

    # open is decided by typeshed
    # def open(*args, **kwargs):
    #     return Value.make_any()

    def ord(c):
        return type_2_value(Int_Type())

    def pow(base, exp=None, mod=None):
        return type_2_value(Int_Type())

    def print(*args, **kwargs):
        return type_2_value(None_Instance)

    # property is in another file

    def repr(object):
        return type_2_value(Str_Type())

    def reversed(self):
        return self

    def round(*args, **kwargs):
        return type_2_value(Int_Type())

    # set is in another file

    def setattr(*args, **kwargs):
        return Value.make_any()

    # slice is typeshed defined

    def sorted(iterable, key=None, reverse=False):
        return iterable

    # static method is in another file

    def str(*args, **kwargs):
        return type_2_value(Str_Type())

    def sum(*args, **kwargs):
        return type_2_value(Int_Type())

    # super is in another file
    # tuple same
    # type same

    def vars(object=None):
        value = Value()
        value.inject(Dict_Instance)
        return value

    def zip(*iterables):
        return Value.make_any()

    def __import__(*args, **kwargs):
        return Value.make_any()

    methods = builtins.filter(
        lambda symbol: builtins.isinstance(symbol, FunctionType),
        builtins.locals().values(),
    )
    for method in methods:
        arti_method = ArtificialFunction(
            tp_function=method, tp_qualname=f"builtins.{method.__name__}"
        )
        artificial_namespace.write_local_value(
            method.__name__, type_2_value(arti_method)
        )


_setup()


def _resolve_name(name, package, level):
    """Resolve a relative module name to an absolute one."""
    bits = package.rsplit(".", level - 1)
    if len(bits) < level:
        raise ValueError("attempted relative import beyond top-level package")
    base = bits[0]
    return "{}.{}".format(base, name) if name else base


def import_a_module(name, package=None, level=0) -> Value:
    import isort

    value = Value()
    category = isort.place_module(name)
    # DEFAULT: Tuple[str, ...] = (FUTURE, STDLIB, THIRDPARTY, FIRSTPARTY, LOCALFOLDER)
    if category == "FUTURE":
        module = Value.make_any()
    elif category == "STDLIB":
        if name == "typing" or name == "typing_extensions":
            module = Value.make_any()
        else:
            module = import_a_module_from_typeshed(name)
    else:
        if not name.startswith(sys.first_party):
            return Value.make_any()
        else:
            module = import_module(name)

    value.inject(module)
    return value
