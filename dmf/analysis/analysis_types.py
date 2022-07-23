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
from dmf.analysis.namespace import Namespace
from dmf.analysis.value import Value


def Py_TYPE(obj):
    return obj.nl__class__


def PyType_Lookup(tp, name):
    mro = tp.nl__mro__
    for cls in mro:
        dict = cls.nl__dict__
        if name in dict:
            val = dict.read_value(name)
            return val
    return None


def PyDescr_IsData(descr):
    f_tp = Py_TYPE(descr)
    f = PyType_Lookup(f_tp, "__set__")
    if f is not None:
        return True
    f = PyType_Lookup(f_tp, "__delete__")
    if f is not None:
        return True
    return False


class MetaAnalysisType(type):
    def __init__(cls, name, bases, dict):
        super().__init__(name, bases, dict)
        cls.nl__dict__ = Namespace()
        cls.nl__name__ = ClassStr()

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self


class Meta(metaclass=MetaAnalysisType):
    pass


class ClassObject(Meta):
    nl__dict__ = Namespace()


def __getattribute__(self, name):
    res = Value()

    tp = Py_TYPE(self)
    descrs = PyType_Lookup(tp, name)
    if descrs is not None:
        assert len(descrs) == 1, descrs
        for descr in descrs:
            if isinstance(descr, ClassFunction):
                pass
            elif isinstance(descr, ClassBuiltinFunction):
                pass
            else:
                f_tp = Py_TYPE(descr)
                fs = PyType_Lookup(f_tp, "__get__")
                if fs is not None:
                    assert len(fs) == 1, fs
                    for f in fs:
                        if PyDescr_IsData(descr):
                            if isinstance(f, ClassFunction):
                                f_method = ClassMethod()
                                res.inject(f_method)
                            elif isinstance(f, ClassBuiltinFunction):
                                f_builtin_method = ClassBuiltinMethod()
                                res.inject(f_builtin_method)
                            else:
                                assert False, f
        if len(res) != 0:
            return res
    if hasattr(self, "nl__dict__"):
        dict = self.nl__dict__
        if name in dict:
            res = self.nl__dict__.read_value(name)
            return res

    if descrs is not None:
        assert len(descrs) == 1, descrs
        for descr in descrs:
            if isinstance(descr, ClassFunction):
                f_method = ClassMethod()
                res.inject(f_method)
            elif isinstance(descr, ClassBuiltinFunction):
                f_builtin_method = ClassBuiltinMethod()
                res.inject(f_builtin_method)
            else:
                f_tp = Py_TYPE(descr)
                fs = PyType_Lookup(f_tp, "__get__")
                if fs is not None:
                    assert len(fs) == 1, fs
                    for f in fs:
                        if isinstance(f, ClassFunction):
                            f_method = ClassMethod()
                            res.inject(f_method)
                        else:
                            assert False, f
        if len(res) != 0:
            return res

    if descrs is not None:
        return descrs

    raise AttributeError


def __setattr__(self, name, value):
    res = Value()

    tp = Py_TYPE(self)
    descrs = PyType_Lookup(tp, name)

    if descrs is not None:
        assert len(descrs) == 1, descrs
        for descr in descrs:
            f_tp = Py_TYPE(descr)
            fs = PyType_Lookup(f_tp, "__set__")
            if fs is not None:
                assert len(fs) == 1, fs
                for f in fs:
                    if isinstance(f, ClassFunction):
                        f_method = ClassMethod()
                        res.inject(f_method)
                    elif isinstance(f, ClassBuiltinFunction):
                        f_builtin_method = ClassBuiltinMethod()
                        res.inject(f_builtin_method)
                    else:
                        assert False, f
        if len(res) != 0:
            return res

    dict = self.nl__dict__
    if value is None:
        dict.del_local_var(name)
    else:
        dict.write_local_var(name, value)
    return res


_value = Value()
_value.inject(__getattribute__)
ClassObject.nl__dict__.write_local_value("__getattribute__", _value)
_value = Value()
_value.inject(__setattr__)
ClassObject.nl__dict__.write_local_value("__setattr__", _value)


class ClassType(Meta):
    pass


class Class(Meta):
    pass


class Module(Meta):
    pass


class ClassFunction(Meta):
    pass


class ClassBuiltinFunction(Meta):
    def __init__(self, function):
        pass


class ClassMethod(Meta):
    pass


class ClassBuiltinMethod(Meta):
    pass


class ClassNone(Meta):
    pass


class ClassBool(Meta):
    pass


class ClassInt(Meta):
    pass


class ClassFloat(Meta):
    pass


class ClassComplex(Meta):
    pass


class ClassSlice(Meta):
    pass


class ClassRange(Meta):
    pass


class ClassStr(Meta):
    pass


class ClassBytes(Meta):
    pass
