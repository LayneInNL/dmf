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


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Singleton(metaclass=SingletonMeta):
    pass


class TypeBool(Singleton):
    fallback_module = "builtins"
    fallback_name = "bool"

    def __init__(self):
        pass


class TypeInt(Singleton):
    fallback_module = "builtins"
    fallback_name = "int"


class TypeFloat(Singleton):
    fallback_module = "builtins"
    fallback_name = "float"


class TypeComplex(Singleton):
    fallback_module = "builtins"
    fallback_name = "complex"


class TypeNone(Singleton):
    pass


class TypeBytes(Singleton):
    fallback_module = "builtins"
    fallback_name = "bytes"


class TypeByteArray(Singleton):
    fallback_module = "builtins"
    fallback_name = "bytearray"
