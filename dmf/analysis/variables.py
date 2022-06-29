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
Namespace_Local = "local"
Namespace_Nonlocal = "nonlocal"
Namespace_Global = "global"
Namespace_Helper = "helper"
POSITION_FLAG = "POSITION_FLAG"
INIT_FLAG = "INIT_FLAG"
RETURN_FLAG = "RETURN_FLAG"


class Var:
    def __init__(self, name: str):
        self.name = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other: Var):
        return self.name == other.name


class LocalVar(Var):
    def __init__(self, name: str):
        super().__init__(name)

    def __repr__(self):
        return f"({self.name}, {Namespace_Local})"


class NonlocalVar(Var):
    def __init__(self, name: str):
        super().__init__(name)

    def __repr__(self):
        return f"({self.name}, {Namespace_Nonlocal})"


class GlobalVar(Var):
    def __init__(self, name: str):
        super().__init__(name)

    def __repr__(self):
        return f"({self.name}, {Namespace_Global})"


class HelperVar(Var):
    def __init__(self, name: str):
        super().__init__(name)

    def __repr__(self):
        return f"({self.name}, helper)"
