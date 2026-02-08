# Simple Dice 插件 - LLM DM 功能设计文档

## 1. 概述

### 1.1 目标
将 Simple Dice 插件从纯骰子工具扩展为 LLM 可用的 **DM（地下城主）工具集**，使 LLM 能够：
- 追踪和管理用户角色卡（User Character）
- 读取/修改用户属性
- 结合骰子进行 RPG 判定
- 维护游戏状态

### 1.2 核心能力
| 功能 | 描述 |
|------|------|
| 角色卡管理 | 创建、读取、更新、删除用户角色 |
| 属性操作 | HP、属性值、技能、物品等 |
| 状态追踪 | 生命值变化、经验值、等级等 |
| 骰子集成 | 属性检定、攻击判定、伤害投骰 |

---

## 2. 系统架构

### 2.1 目录结构
```
simple_dice/
├── main.py              # 主逻辑（保持极简）
├── data/
│   ├── __init__.py
│   ├── storage.py       # 存储抽象层
│   └── character.py     # 角色数据模型
├── tools/
│   ├── __init__.py
│   ├── character_tools.py   # LLM 角色操作工具
│   └── dice_tools.py        # LLM 骰子工具（重构）
└── utils/
    ├── __init__.py
    └── validators.py        # 属性验证
```

### 2.2 数据流
```
LLM 调用工具
    │
    ▼
┌─────────────────────────────────────┐
│         LLM Tool Interface          │
│  get_character / update_character   │
│  roll_check / combat_action         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│         Storage Layer               │
│  JSON 文件存储（轻量、无依赖）        │
│  支持多用户、多角色隔离               │
└─────────────────────────────────────┘
```

---

## 3. 数据模型

### 3.1 Character（角色）
```python
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime

@dataclass
class Character:
    """用户角色卡"""
    id: str                          # 角色唯一ID
    user_id: str                     # 所属用户ID
    name: str                        # 角色名称
    race: str = ""                   # 种族
    class_: str = ""                 # 职业 (class 是关键字)
    level: int = 1                   # 等级
    exp: int = 0                     # 当前经验值

    # 属性点 (DND 风格)
    attributes: Dict[str, int] = field(default_factory=lambda: {
        "力量": 10, "敏捷": 10, "体质": 10,
        "智力": 10, "感知": 10, "魅力": 10
    })

    # 生命值
    hp: int = 10
    max_hp: int = 10
    temp_hp: int = 0                 # 临时生命值

    # 技能
    skills: Dict[str, int] = field(default_factory=dict)

    # 物品栏
    inventory: List[str] = field(default_factory=list)

    # 状态效果
    conditions: List[str] = field(default_factory=list)

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    notes: str = ""                  # 角色描述/背景

    def get_modifier(self, attr: str) -> int:
        """获取属性修正值 (DND 5e 规则: (属性值-10)/2 向下取整)"""
        value = self.attributes.get(attr, 10)
        return (value - 10) // 2
```

### 3.2 DiceRoll（骰子记录）
```python
@dataclass
class DiceRoll:
    """骰子投掷记录"""
    id: str
    character_id: str
    expression: str
    rolls: List[int]
    total: int
    modifier: int = 0
    reason: str = ""                 # 投掷原因
    timestamp: datetime = field(default_factory=datetime.now)
    is_hidden: bool = False
```

### 3.3 GameSession（游戏会话）
```python
@dataclass
class GameSession:
    """游戏会话（可选：用于追踪团进）"""
    id: str
    characters: List[str]            # 参与角色ID
    dm_user_id: str                  # DM 用户ID
    started_at: datetime = field(default_factory=datetime.now)
    scene: str = ""                  # 当前场景描述
    turn_order: List[str] = field(default_factory=list)
```

---

## 4. 存储方案

### 4.1 JSON 文件存储
```python
# data/storage.py
import json
import os
from pathlib import Path
from typing import Optional

class JsonStorage:
    """轻量级 JSON 存储"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.characters_file = self.data_dir / "characters.json"
        self.rolls_file = self.data_dir / "rolls.json"

    def load_characters(self) -> Dict[str, Character]:
        """加载所有角色"""
        if not self.characters_file.exists():
            return {}
        with open(self.characters_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {
                uid: Character(**char_data)
                for uid, char_data in data.items()
            }

    def save_character(self, character: Character) -> None:
        """保存角色"""
        characters = self.load_characters()
        characters[character.id] = character.model_dump()
        with open(self.characters_file, 'w', encoding='utf-8') as f:
            json.dump(characters, f, ensure_ascii=False, indent=2, default=str)

    def get_character_by_user(self, user_id: str) -> Optional[Character]:
        """根据用户ID获取角色"""
        characters = self.load_characters()
        for char in characters.values():
            if char.user_id == user_id:
                return Character(**char)
        return None
```

### 4.2 数据隔离
- **用户级隔离**: 一个用户对应一个角色（简化设计）
- **群聊隔离**: 可选支持 `group_id` 字段区分不同群聊的角色

---

## 5. LLM Tool 接口设计

### 5.1 角色管理工具

#### 5.1.1 创建角色
```python
@filter.llm_tool(name="create_character")
async def create_character(
    self,
    event: AstrMessageEvent,
    name: str,
    race: str = "",
    class_: str = "",
    attributes: Optional[Dict[str, int]] = None,
    hp: int = 10
) -> str:
    '''为用户创建一个新的角色卡。

    Args:
        name(str): 角色名称
        race(str, optional): 种族，如 "人类"、"精灵"、"矮人"
        class_(str, optional): 职业，如 "战士"、"法师"、"盗贼"
        attributes(dict, optional): 初始属性，格式 {"力量": 14, "敏捷": 12, ...}
        hp(int, optional): 初始生命值，默认10
    '''
    # 验证属性值范围 (1-20)
    # 创建角色并保存
    # 返回创建结果
```

#### 5.1.2 获取角色信息
```python
@filter.llm_tool(name="get_character")
async def get_character(
    self,
    event: AstrMessageEvent,
    user_id: Optional[str] = None
) -> str:
    '''获取当前用户或指定用户的角色卡信息。

    Args:
        user_id(str, optional): 用户ID，不提供则获取当前用户角色
    '''
    # 返回格式化的角色属性面板
```

#### 5.1.3 更新角色属性
```python
@filter.llm_tool(name="update_character")
async def update_character(
    self,
    event: AstrMessageEvent,
    user_id: Optional[str] = None,
    attribute: Optional[str] = None,
    value: Optional[int] = None,
    hp_change: Optional[int] = None,      # HP 变化（正/负）
    set_hp: Optional[int] = None,         # 直接设置 HP
    add_skill: Optional[str] = None,      # 添加技能
    add_item: Optional[str] = None,        # 添加物品
    add_condition: Optional[str] = None,   # 添加状态
    remove_condition: Optional[str] = None # 移除状态
) -> str:
    '''修改角色的属性、生命值、技能、物品或状态。

    至少提供一个修改参数。

    Examples:
        - update_character(hp_change=-5)  # 受伤 5 点
        - update_character(hp_change=3)    # 回复 3 点
        - update_character(attribute="力量", value=16)  # 永久提升力量
    '''
```

### 5.2 骰子检定工具（增强版）

#### 5.2.1 属性检定
```python
@filter.llm_tool(name="ability_check")
async def ability_check(
    self,
    event: AstrMessageEvent,
    ability: str,                    # 如 "力量"、"敏捷"
    user_id: Optional[str] = None,
    advantage: bool = False,        # 优势
    disadvantage: bool = False,     # 劣势
    hidden: bool = False,
    reason: str = ""
) -> str:
    '''进行属性检定（1d20 + 属性修正值）。

    Args:
        ability(str): 属性名称，支持中文或英文 ("str", "dex", 等)
        advantage(bool): 优势（投两次取高），默认 False
        disadvantage(bool): 劣势（投两次取低），默认 False
        hidden(bool): 是否暗投，默认 False
        reason(str): 检定原因，用于日志
    '''
    # 1. 获取角色属性
    # 2. 投掷 1d20（支持优势/劣势）
    # 3. 计算修正值
    # 4. 返回结果
```

#### 5.2.2 攻击检定
```python
@filter.llm_tool(name="attack_roll")
async def attack_roll(
    self,
    event: AstrMessageEvent,
    weapon_name: str,               # 武器名称
    attack_bonus: int = 0,          # 攻击加值
    damage_dice: str = "1d8",        # 伤害骰子
    damage_bonus: int = 0,          # 伤害加值
    hidden: bool = False
) -> str:
    '''进行攻击投掷并计算伤害。

    Args:
        weapon_name(str): 武器名称
        attack_bonus(int): 攻击加值（如属性修正+熟练）
        damage_dice(str): 伤害骰子表达式，如 "1d8"、"2d6"
        damage_bonus(int): 伤害加值
        hidden(bool): 是否暗投，默认 False
    '''
```

#### 5.2.3 恢复生命值
```python
@filter.llm_tool(name="heal")
async def heal(
    self,
    event: AstrMessageEvent,
    amount: int,
    user_id: Optional[str] = None
) -> str:
    '''为角色恢复生命值（不超过最大值）。

    Args:
        amount(int): 恢复量
        user_id(str, optional): 目标用户ID
    '''
```

### 5.3 战斗工具

```python
@filter.llm_tool(name="combat_damage")
async def combat_damage(
    self,
    event: AstrMessageEvent,
    target_user_id: str,
    damage: int,
    damage_type: str = "物理"       # 物理、魔法、酸、火、冰等
) -> str:
    '''对目标造成伤害。

    Args:
        target_user_id(str): 目标用户ID
        damage(int): 伤害值
        damage_type(str): 伤害类型
    '''
```

---

## 6. 用户命令设计

### 6.1 角色命令
| 命令 | 功能 |
|------|------|
| `/char create <名字> [种族] [职业]` | 创建角色 |
| `/char show` | 显示当前角色 |
| `/char hp <±值>` | 修改 HP |
| `/char attr <属性> <值>` | 设置属性 |
| `/char add <物品>` | 添加物品 |
| `/char condition <状态>` | 添加状态效果 |

### 6.2 检定命令
| 命令 | 功能 |
|------|------|
| `/check <属性>` | 属性检定 |
| `/save <属性>` | 豁免检定 |
| `/attack <武器>` | 攻击投掷 |
| `/init` | 敏捷投掷决定先攻 |

---

## 7. 消息格式示例

### 7.1 角色面板
```
┌─────────────────────────────┐
│ 🧙‍♂️ 阿尔温 (精灵法师) Lv.3 │
├─────────────────────────────┤
│ HP: 15/18  🛡️ 临时: 5        │
│ 经验: 450/900               │
├─────────────────────────────┤
│ 力量  8  [-1]    敏捷 14 [+2]│
│ 体质 12 [+1]    智力 16 [+3]│
│ 感知 10 [+0]    魅力 13 [+1]│
├─────────────────────────────┤
│ 技能: 隐蔽(+4), 奥秘(+5)     │
│ 物品: 法杖, 治疗药水×2      │
│ 状态: -                     │
└─────────────────────────────┘
```

### 7.2 检定结果
```
🔮 阿尔温 进行「智力」检定
   1d20 [+3] = [15] + 3 = 18
   ✅ 成功！
```

### 7.3 攻击结果
```
⚔️ 阿尔温 使用「火焰射线」攻击哥布林
   攻击: 1d20 [+5] = [12] + 5 = 17 → 命中！
   伤害: 2d10 [+3] = [6,4] + 3 = 13 🔥 火焰伤害
   哥布林 HP: 13/30
```

---

## 8. 实现优先级

### Phase 1: 基础角色系统
- [ ] Character 数据模型
- [ ] JSON 存储层
- [ ] 创建/读取角色
- [ ] HP 管理

### Phase 2: 骰子集成
- [ ] 属性检定 (ability_check)
- [ ] 攻击投掷 (attack_roll)
- [ ] 优势/劣势支持

### Phase 3: 战斗系统
- [ ] 伤害/治疗工具
- [ ] 状态效果管理
- [ ] 生命值上限检查

### Phase 4: 高级功能
- [ ] 技能系统
- [ ] 物品栏管理
- [ ] 经验/等级系统
- [ ] 先攻排序

---

## 9. 技术要点

### 9.1 事件对象获取用户ID
```python
# 从 event 获取用户/群聊信息
user_id = event.get_user_id()
group_id = event.get_group_id() if hasattr(event, 'get_group_id') else None
```

### 9.2 消息发送
```python
# 发送富文本消息
yield event.plain_result(formatted_message)

# 或使用 Markdown
event.set_result(MessageEventResult(chain=[Comp.Markdown(content)]))
```

### 9.3 错误处理
```python
try:
    # 操作
except CharacterNotFoundError:
    return "未找到角色，请先创建角色"
except ValueError as e:
    return f"数值错误: {str(e)}"
```

---

## 10. 扩展建议

1. **多角色支持**: 改为列表存储，一个用户可有多角色
2. **职业/种族模板**: 预设属性和技能
3. **掷骰日志**: 记录历史用于查询
4. **存档导入/导出**: JSON 格式备份
5. **数据库存储**: 替换为 SQLite（可选）
