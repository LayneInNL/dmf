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


# class Test:
#     def __init__(self):
#         pass
#
#     def test(self):
#         return self
#
#
# a = Test()
# res = a.test()
# a.x = 1
# y = a.x
# a.x = 1
# b = a.x


class Base:
    def test(self):
        return 1


class Derive(Base):
    def test(self):
        return super(Derive, self).test()


d = Derive()
res = d.test()
