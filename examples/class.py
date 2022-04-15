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

x = 1
y = x


class Test:
    a = 1
    b = False

    def __init__(self):
        self.c = 1
        self.d = Test.a
        self.f = Test.e

    e = None
    for x in [1, 2, 3]:
        print(x)


t = Test()

t.e = 2
Test.e = 3
print(t.x)

t2 = Test()
print(t2.e == t.e)
print(t2.a == t.a)
