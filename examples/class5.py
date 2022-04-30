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
import class3

print(dir())


class Test(class3.Test):
    class5_test = 666

    def __init__(self):
        pass

    def test(self):
        Test.class5_test = "111"
        print(class3.Test.__mro__)
        print(self.xxx)
        print(dir())
        print(Test)


t = Test()

t.class5_test = 555
Test.class5_test = "str"
t.test()
