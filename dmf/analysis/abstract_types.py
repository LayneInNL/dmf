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

from abc import ABC, ABCMeta, abstractmethod

from dmf.analysis.c3 import c3
from dmf.analysis.namespace import Namespace


class SingletonMeta(ABCMeta):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Singleton(metaclass=SingletonMeta):
    pass


class TypeAny(Singleton):
    def __repr__(self):
        return "Any"


class TypeInt:
    def __init__(self):
        pass

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeFloat:
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeComplex:
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeBool:
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeNone:
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeStr:
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeBytes:
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class TypeByteArray:
    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class LatticeOperation(ABCMeta):
    @abstractmethod
    def __le__(self, other):
        ...

    @abstractmethod
    def __iadd__(self, other):
        ...


def _py_type(obj):
    return obj.tp_class


# https://github.com/python/cpython/blob/3.7/Objects/typeobject.c
def _pytype_lookup(type, name: str):
    res = _find_name_in_mro(type, name)
    return res


# https://github.com/python/cpython/blob/3.7/Objects/typeobject.c
def _find_name_in_mro(type, name: str):
    res = None

    mro = type.tp_mro
    for base in mro:
        dict = base.tp_uuid
        if name in dict:
            return dict[name]
    return res


def address_getters(descrs):
    for descr in descrs:
        # a set of parent types of class attributes
        descr_tp = _py_type(descr)
        descr_tp_get = descr_tp.tp_get
        if descr_tp_get is not NotImplemented:
            pass


def _PyObject_GenericGetAttr(obj, name: str):
    # the parent type
    tp = _py_type(obj)
    # a set of class attributes on the parent type
    descrs = _pytype_lookup(tp, name)
    for descr in descrs:
        # a set of parent types of class attributes
        descr_tp = _py_type(descr)
        descr_tp_get = descr_tp.tp_get
        if descr_tp_get is not NotImplemented:
            pass


class TypeType(metaclass=LatticeOperation):
    def __init__(self):
        self._uuid_ = id(type(self))
        self.dict = {}

    @property
    def _uuid_(self):
        return self._uuid

    @_uuid_.setter
    def _uuid_(self, uuid):
        self._uuid = uuid

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]


class TypeSlots(metaclass=LatticeOperation):
    def __init__(self):
        self.tp_uuid = NotImplemented
        self.tp_name = NotImplemented
        self.tp_getattro = NotImplemented
        self.tp_getattr = NotImplemented
        self.tp_setattro = NotImplemented
        self.tp_dict = NotImplemented
        self.tp_class = NotImplemented
        self.tp_mro = NotImplemented

        self.tp_get = NotImplemented
        self.tp_set = NotImplemented
        self.tp_delete = NotImplemented


class TypeObject(TypeSlots):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(type(self))
        self.tp_dict = {}

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]

    def _setup(self):
        def __init__(self):
            return self

        def __getattribute__(self, name: str):
            pass


class TypeAnalysisFunction(TypeSlots):
    def __init__(self, uuid):
        super().__init__()
        self.tp_uuid = uuid

    def __le__(self, other):
        pass

    def __iadd__(self, other):
        pass


class TypeArtificialFunction(TypeSlots):
    pass


class TypeAnalysisMethod(TypeSlots):
    def __init__(self):
        pass


class TypeArtificialMethod:
    pass


class TypeAnalysisClass(TypeSlots):
    def __init__(self, uuid, bases):
        super().__init__()
        self.tp_uuid = uuid
        self.tp_bases = bases
        self.tp_mro = c3(self)
        self.tp_dict = Namespace()

    def __le__(self, other):
        return self.tp_dict <= other.tp_uuid

    def __iadd__(self, other):
        self.tp_dict += other.tp_uuid
        return self


class TypeInstance:
    pass
