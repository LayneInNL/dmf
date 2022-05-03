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

# https://zhuanlan.zhihu.com/p/151856162


def c3MRO(cls):
    if cls is object:
        # 讨论假设顶层基类为object，递归终止
        return [object]

    # 构造C3-MRO算法的总式，递归开始
    merge_list = [c3MRO(baseCls) for baseCls in cls.__bases__]
    merge_list.append(list(cls.__bases__))
    mro = [cls] + merge(merge_list)
    return mro


def merge(in_lists):
    if not in_lists:
        # 若合并的内容为空，返回空list
        # 配合下文的排除空list操作，递归终止
        return []

    # 遍历要合并的mro
    for mroList in in_lists:
        # 取head
        head = mroList[0]
        # 遍历要合并的mro（与外一层相同），检查尾中是否有head
        ### 此处也遍历了被取head的mro，严格地来说不符合标准算法实现
        ### 但按照多继承中地基础规则（一个类只能被继承一次），
        ### head不可能在自己地尾中，无影响，若标准实现，反而增加开销
        for cmpList in in_lists[in_lists.index(mroList) + 1 :]:
            if head in cmpList[1:]:
                break
        else:
            # 筛选出好head
            next_list = []
            for mergeItem in in_lists:
                if head in mergeItem:
                    mergeItem.remove(head)
                if mergeItem:
                    # 排除空list
                    next_list.append(mergeItem)
            # 递归开始
            return [head] + merge(next_list)
    else:
        # 无好head，引发类型错误
        raise TypeError
