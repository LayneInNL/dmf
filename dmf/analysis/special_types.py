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


class SingletonInstance(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonInstance, cls).__call__(
                *args, **kwargs
            )
        return cls._instances[cls]


class SingletonInstanceWithDeepcopy:
    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]


class _TypeAny(SingletonInstanceWithDeepcopy, metaclass=SingletonInstance):
    def __init__(self):
        self.tp_uuid = -1024
        self.tp_class = self
        self.tp_bases = [[self]]

    def __repr__(self):
        return "Any"

    def __le__(self, other):
        return True

    def __iadd__(self, other):
        return self

    # Any[xxx]
    def __getitem__(self, item):
        return self

    def __getattr__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return self

    def values(self):
        return [self]

    def __iter__(self):
        return iter([self])

    def extract_type(self):
        return "Any"


# mimic typing.Any
Any = _TypeAny()
