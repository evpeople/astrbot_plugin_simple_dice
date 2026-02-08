# Simple Dice 插件 - KV 存储设计文档

## 1. 目标

为 LLM 提供简单的键值存储能力，使其能追踪用户属性、游戏状态等。

## 2. 存储结构

```
data/kv.json
{
  "user_123": {
    "hp": 15,
    "max_hp": 20,
    "str": 14,
    "inventory": ["长剑", "治疗药水"],
    "role": "战士"
  },
  "group_456": {
    "scene": "地下城入口",
    "npcs": ["哥布林", "地精"]
  }
}
```

## 3. LLM 工具

### 3.1 kv_read - 读取值
```python
@filter.llm_tool(name="kv_read")
async def kv_read(
    self,
    event: AstrMessageEvent,
    key: str,
    user_id: Optional[str] = None,
    scope: str = "user"  # "user" 或 "group"
) -> str:
    '''读取指定键的值。

    Args:
        key: 要读取的键名
        scope: 作用域，"user" 或 "group"
    '''
```

### 3.2 kv_write - 写入值
```python
@filter.llm_tool(name="kv_write")
async def kv_write(
    self,
    event: AstrMessageEvent,
    key: str,
    value: Any,
    scope: str = "user"
) -> str:
    '''写入键值对。

    Args:
        key: 键名
        value: 要存储的值（支持数字、字符串、列表、字典）
        scope: 作用域
    '''
```

### 3.3 kv_update - 更新数值
```python
@filter.llm_tool(name="kv_update")
async def kv_update(
    self,
    event: AstrMessageEvent,
    key: str,
    delta: int,  # 变化量
    scope: str = "user"
) -> str:
    '''对数值进行增减操作（用于 HP、经验值等）。

    Args:
        key: 键名
        delta: 变化量，正数增加，负数减少
    '''
```

### 3.4 kv_list - 列出所有键
```python
@filter.llm_tool(name="kv_list")
async def kv_list(
    self,
    event: AstrMessageEvent,
    scope: str = "user"
) -> str:
    '''列出指定作用域下的所有键值对。
    '''
```

## 4. 存储后端

```python
# data/kv_storage.py
import json
from pathlib import Path
from typing import Any, Dict, Optional

class KVStorage:
    def __init__(self, data_dir: str = "data"):
        self.file = Path(data_dir) / "kv.json"
        self.file.parent.mkdir(exist_ok=True)
        if not self.file.exists():
            self.file.write_text("{}", encoding="utf-8")

    def _load(self) -> Dict[str, dict]:
        return json.loads(self.file.read_text(encoding="utf-8"))

    def _save(self, data: dict):
        self.file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, scope: str, key: str, user_id: str) -> Any:
        data = self._load()
        return data.get(user_id if scope == "user" else user_id, {}).get(key)

    def set(self, scope: str, key: str, value: Any, user_id: str):
        data = self._load()
        storage_id = user_id if scope == "user" else user_id
        if storage_id not in data:
            data[storage_id] = {}
        data[storage_id][key] = value
        self._save(data)

    def update_numeric(self, scope: str, key: str, delta: int, user_id: str) -> int:
        data = self._load()
        storage_id = user_id if scope == "user" else user_id
        if storage_id not in data:
            data[storage_id] = {}
        current = data[storage_id].get(key, 0)
        new_value = current + delta
        data[storage_id][key] = new_value
        self._save(data)
        return new_value

    def list_all(self, scope: str, user_id: str) -> dict:
        data = self._load()
        storage_id = user_id if scope == "user" else user_id
        return data.get(storage_id, {})
```

## 5. 使用示例

| LLM 操作 | 结果 |
|---------|------|
| `kv_write("hp", 15)` | hp = 15 |
| `kv_read("hp")` | 返回 15 |
| `kv_update("hp", -5)` | hp = 10 |
| `kv_write("inventory", ["剑"])` | inventory = ["剑"] |
| `kv_list()` | {"hp": 10, "inventory": ["剑"]} |
