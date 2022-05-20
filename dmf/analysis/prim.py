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
from __future__ import annotations

#  limitations under the License.
from dmf.log.logger import logger


class Prim:
    pass


class Int(Prim):
    def __init__(self):
        pass

    def __le__(self, other: Int):
        return True

    def __iadd__(self, other: Int):
        return self

    def __repr__(self):
        return "int"

    def setattr(self, key, value):
        logger.warning("set attr to int, ignore")
        assert False

    def getattr(self, key):
        logger.warning("get attr from int, ignore")
        assert False


class Bool(Prim):
    def __init__(self):
        pass

    def __le__(self, other: Bool):
        return True

    def __iadd__(self, other: Bool):
        return self

    def __repr__(self):
        return "bool"

    def setattr(self, key, value):
        logger.warning("set attr to bool, ignore")
        assert False

    def getattr(self, key):
        logger.warning("get attr from bool, ignore")
        assert False


class NoneType(Prim):
    def __init__(self):
        pass

    def __le__(self, other: NoneType):
        return True

    def __iadd__(self, other):
        return self

    def __repr__(self):
        return "None"

    def setattr(self, key, value):
        logger.warning("set attr to none, ignore")
        assert False

    def getattr(self, key):
        logger.warning("set attr from none, ignore")
        assert False


class Str(Prim):
    def __init__(self):
        pass

    def __le__(self, other: Str):
        return True

    def __iadd__(self, other: Str):
        return self

    def __repr__(self):
        return "str"

    def setattr(self, key, value):
        logger.warning("set attr to none, ignore")
        assert False

    def getattr(self, key):
        logger.warning("set attr from none, ignore")
        assert False


class Bytes(Prim):
    def __init__(self):
        pass

    def __le__(self, other: Bytes):
        return True

    def __iadd__(self, other: Bytes):
        return self

    def __repr__(self):
        return "bytes"

    def setattr(self, key, value):
        logger.warning("set attr to none, ignore")
        assert False

    def getattr(self, key):
        logger.warning("set attr from none, ignore")
        assert False


PRIM_INT = Int()
PRIM_INT_ID = id(PRIM_INT)
PRIM_BOOL = Bool()
PRIM_BOOL_ID = id(PRIM_BOOL)
PRIM_NONE = NoneType()
PRIM_NONE_ID = id(PRIM_NONE)
PRIM_STR = Str()
PRIM_STR_ID = id(PRIM_STR)
PRIM_BYTES = Bytes()
PRIM_BYTES_ID = id(PRIM_BYTES)
