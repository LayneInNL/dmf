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

from unittest import TestCase

from dmf.analysis.obsolete.prim import (
    PRIM_NONE,
    PRIM_BOOL,
    PRIM_NUM,
    PRIM_BYTE,
    PRIM_STR,
)
from dmf.analysis.value import _Value, FuncObj, ClsType


class TestValue(TestCase):
    def test_inject_heap_type(self):
        value = _Value()
        value.inject_heap_type(1)
        heaps = value.extract_heap_types()
        s = {1}
        self.assertEqual(heaps, s)

    def test_inject_none(self):
        value = _Value()
        value.inject_none()
        self.assertEqual(value.extract_prim_types(), {PRIM_NONE})

    def test_inject_bool(self):
        value = _Value()
        value.inject_bool()
        self.assertEqual(value.extract_prim_types(), {PRIM_BOOL})

    def test_inject_num(self):
        value = _Value()
        value.inject_num()
        self.assertEqual(value.extract_prim_types(), {PRIM_NUM})

    def test_inject_byte(self):
        value = _Value()
        value.inject_byte()
        self.assertEqual(value.extract_prim_types(), {PRIM_BYTE})

    def test_inject_str(self):
        value = _Value()
        value.inject_str()
        self.assertEqual(value.extract_prim_types(), {PRIM_STR})

    def test_inject_str2(self):
        value = _Value()
        value.inject_str()
        value.inject_str()
        self.assertEqual(value.extract_prim_types(), {PRIM_STR})

    def test_inject_func_type(self):
        value = _Value()
        value.inject_func_type(1, 2, 3, None)
        value.inject_func_type(1, 2, 3, None)
        res = value.extract_func_types()
        func_obj = FuncObj(1, 2, 3, None)
        self.assertEqual(res, {func_obj})

    def test_inject_class_type(self):
        value = _Value()
        value.inject_class_type(1, "test", [], {})
        value.inject_class_type(1, "test", [], {})
        res = value.extract_class_types()
        cls_obj = ClsType(1, "test", [], {})
        self.assertEqual(res, {cls_obj})
