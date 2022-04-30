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

import dis


class Base:
    xxx = 1
    pass


class Test(Base):
    def __init__(self):
        print(Base)
        print(Test)


print(dis.dis(Test.__init__))

print(id(Test))
a = Test()
print(id(a))
print(Test.__bases__)
print(id(Test.__base__))
pass

print(Test.__base__)
print(Test.__mro__)
