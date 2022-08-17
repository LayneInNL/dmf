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


Type_Type = TypeType()


class TypeObject(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self]


Object_Type = TypeObject()
Type_Type.tp_mro = [Type_Type, Object_Type]


class TypeInt(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Int_Type = TypeInt()


class TypeFloat(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Float_Type = TypeFloat()


class TypeComplex(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Complex_Type = TypeComplex()


class TypeList(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


List_Type = TypeList()


class TypeTuple(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Tuple_Type = TypeTuple()


class TypeRange(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Range_Type = TypeRange()


class TypeStr(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Str_Type = TypeStr()


class TypeBytes(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Bytes_Type = TypeBytes()


class TypeByteArray(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


ByteArray_Type = TypeByteArray()


class TypeMemoryView(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


MemoryView_Type = TypeMemoryView()


class TypeSet(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Set_Type = TypeSet()


class TypeFrozenSet(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


FrozenSet_Type = TypeFrozenSet()


class TypeDict(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Dict_Type = TypeDict()


class TypeModule(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Module_Type = TypeModule()


class TypeFunction(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Function_Type = TypeFunction()


class TypeMethod(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Method_Type = TypeMethod()


class TypeNoneType(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


None_Type = TypeNoneType()


class TypeBool(SpecialAttributes):
    def __init__(self):
        super().__init__()
        self.tp_uuid = id(self)
        self.tp_dict = Namespace()
        self.tp_class = Type_Type
        self.tp_mro = [self, Object_Type]


Bool_Type = TypeBool()
