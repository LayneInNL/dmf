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


class SpecialAttributes:
    def __init__(self):
        self.tp_uuid = NotImplemented
        self.tp_dict = NotImplemented
        self.tp_class = NotImplemented
        self.tp_mro = NotImplemented
        # self.tp_bases = NotImplemented
        # self.tp_name = NotImplemented
        # self.tp_qualname = NotImplemented


class TypeType(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = self


Type = TypeType()


class TypeObject(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type


Object = TypeObject()
Type.tp_mro = [Type, Object]


class TypeInt(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Int = TypeInt()


class TypeFloat(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Float = TypeFloat()


class TypeComplex(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Complex = TypeComplex()


class TypeList(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


List = TypeList()


class TypeTuple(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Tuple = TypeTuple()


class TypeRange(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Range = TypeRange()


class TypeStr(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Str = TypeStr()


class TypeBytes(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Bytes = TypeBytes()


class TypeByteArray(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


ByteArray = TypeByteArray()


class TypeMemoryView(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


MemoryView = TypeMemoryView()


class TypeSet(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Set = TypeSet()


class TypeFrozenSet(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


FrozenSet = TypeFrozenSet()


class TypeDict(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Dict = TypeDict()


class TypeModule(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Module = TypeModule()


class TypeFunction(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Function = TypeFunction()


class TypeMethod(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Method = TypeMethod()


class TypeNoneType(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


NoneType = TypeNoneType()


class TypeBool(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type
        self.tp_mro = [self, Object]


Bool = TypeBool()
