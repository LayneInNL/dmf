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

from __future__ import annotations

from copy import deepcopy

TOP = "VALUE_TOP"


class Value:
    def __init__(self, *, top=False):
        if top:
            self.type_dict = TOP
        else:
            self.type_dict = {}

    def __bool__(self):
        if isinstance(self.type_dict, dict) and self.type_dict:
            return True
        return False

    def __len__(self):
        if self.type_dict == TOP:
            return -1
        return len(self.type_dict)

    def __le__(self, other: Value):
        if other.type_dict == TOP:
            return True
        if self.type_dict == TOP:
            return False

        for k in self.type_dict:
            if k not in other.type_dict:
                return False
            elif not self.type_dict[k] <= other.type_dict[k]:
                return False
        return True

    def __iadd__(self, other: Value):
        if self.type_dict == TOP or other.type_dict == TOP:
            self.type_dict = TOP
            return self

        for k in other.type_dict:
            if k not in self.type_dict:
                self.type_dict[k] = other.type_dict[k]
            else:
                self.type_dict[k] += other.type_dict[k]
        return self

    def __repr__(self):
        return self.type_dict.__repr__()

    def __iter__(self):
        return iter(self.type_dict.values())

    def __deepcopy__(self, memo):
        self_id = id(self)
        if self_id not in memo:
            value = Value()
            if self.type_dict == TOP:
                value.type_dict = TOP
            else:
                value.type_dict = deepcopy(self.type_dict, memo)
            memo[self_id] = value
        return memo[self_id]

    def inject_type(self, typ):
        self.type_dict[typ.__my_uuid__] = typ

    def inject_value(self, value: Value):
        for lab, typ in value.type_dict.items():
            if lab not in self.type_dict:
                self.type_dict[lab] = typ
            else:
                self.type_dict[lab] += typ


def create_value_with_type(typ) -> Value:
    value = Value()
    value.inject_type(typ)
    return value


def create_value_with_value(val) -> Value:
    value = Value()
    value.inject_value(val)
    return value
