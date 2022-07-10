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
class property:
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.doc = doc

    def __get__(self, instance, owner):
        return self.fget(instance)

    def __set__(self, instance, value):
        return self.fset(instance, value)

    def __delete(self, instance):
        return self.fdel(instance)


class Test:
    def name(self):
        return 1

    def name1(self, value):
        pass

    def name2(self):
        pass

    p = property(name, name1, name2)
