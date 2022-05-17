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
from dmf.analysis.value import AbstractValue


class Int:
    def __init__(self):
        pass

    def bit_length(self):
        return PRIM_INT

    def conjugate(self):
        return PRIM_INT

    def denominator(self):
        return PRIM_INT

    def from_bytes(self):
        return PRIM_INT

    def imag(self):
        pass

    def numerator(self):
        pass

    def real(self):
        pass

    def to_bytes(self):
        pass


class List:
    def __init__(self, iter_types: AbstractValue = None):
        self.abstract_value = AbstractValue()
        if iter_types:
            self.abstract_value += iter_types

    def append(self, elt_type):
        self.abstract_value += elt_type


# builtin objects, we use singleton objects
PRIM_INT = Int()
