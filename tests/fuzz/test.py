# coding: utf-8
import pandas as pd
from dataclasses import dataclass
from woke.development.primitive_types import uint, bytes32
from wokelib.generators.random import st


@dataclass
class T:
    a: int
    b: str


from typing import Callable, DefaultDict, List, Optional, Type, Dict, get_type_hints
from typing_extensions import get_type_hints, get_args, get_origin
from dataclasses import fields

field_names = [field.name for field in fields(T)]
resolved_hints = get_type_hints(T)
resolved_field_types = {name: resolved_hints[name] for name in field_names}
from typing import Any, Dict

# df = pd.DataFrame({c: pd.Series(dtype=t) for c, t in resolved_field_types.items()})
# df
# df.dtypes

a = T(a=5, b="test")

from typing_extensions import get_type_hints, get_args, get_origin
from dataclasses import asdict

asdict(a)

idx = str(st.random_bytes(32, 32)())
idx2 = str(st.random_bytes(32, 32)())
df2 = pd.DataFrame([asdict(a)], index=[idx])


print(df2)
b = T(a=15, b="test")

df2.loc[idx] = asdict(b)

print(df2)
# b = T(a=15, b='testsdfs')
# df2.loc[0]=asdict(b)


class DataModel:
    def __init__(self):
        self._data = pd.DataFrame()

    @property
    def data(self) -> pd.DataFrame:
        return self._data

    def insert_or_update(self, index: Any, data: Any):
        print(type(data))
        values = data if type(data) == dict else asdict(data)
        if self._data.empty:
            self._data = pd.DataFrame([values], index=[index])
        else:
            if index in self._data.index:
                self._data.loc[index] = values
            else:
                self._data = pd.concat(
                    [self._data, pd.DataFrame([values], index=[index])]
                )

    def is_same(self, index: Any, data: Any) -> bool:
        values = data if type(data) == dict else asdict(data)
        if index in self._data.index:
            return self._data.loc[index].to_dict() == values
        return False


dm = DataModel()

dm.insert_or_update(idx, asdict(a))

print(dm._data)

dm.insert_or_update(idx, asdict(b))
print(dm._data)

dm.insert_or_update(idx2, asdict(a))
print(dm._data)


print(dm.is_same(idx2, a))

print(dm.is_same(idx, asdict(a)))

print(dm.data)


def asdict2(t):
    for f in fields(t):
        print(f)

    field_names = {field.name: getattr(t, field.name) for field in fields(t)}
    return field_names


print(asdict2(a))
