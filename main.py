import re
import json
import random
import os
from pathlib import Path
from typing import Any, Dict, Optional
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

# KV 存储文件路径
_KV_FILE = Path(__file__).parent / "data" / "kv.json"


def parse_dice_expression(expr: str) -> tuple[int, list[tuple[int, int]], int]:
    """解析骰子表达式，返回 (加成值, [(个数, 面数)...], 原始表达式)

    例如: "3d10+5" -> (5, [(3, 10)], "3d10+5")
    例如: "2d6-1d4+3" -> (3, [(2, 6), (1, 4)], "2d6-1d4+3")
    """
    expr = expr.strip().lower().replace(" ", "")

    # 处理括号
    if "(" in expr or ")" in expr:
        return (0, [], expr)

    # 匹配 NdM 格式 (例如: 3d10, d6, 2D20)
    dice_pattern = r'(\d*)d(\d+)'

    # 先找出所有骰子部分
    dice_parts = []
    last_end = 0
    base_value = 0

    # 临时存储表达式用于替换
    temp_expr = expr

    def replace_dice(match):
        nonlocal last_end, base_value
        count = int(match.group(1)) if match.group(1) else 1
        faces = int(match.group(2))
        dice_parts.append((count, faces))
        placeholder = f"__DICE_{len(dice_parts)-1}__"
        return placeholder

    temp_expr = re.sub(dice_pattern, replace_dice, temp_expr)

    # 计算基础值（把所有骰子替换为0后的表达式结果）
    for i in range(len(dice_parts)):
        temp_expr = temp_expr.replace(f"__DICE_{i}__", "0")

    try:
        base_value = eval(temp_expr, {"__builtins__": {}})
    except:
        base_value = 0

    return (base_value, dice_parts, expr)


def roll_dice(count: int, faces: int) -> list[int]:
    """投掷指定数量和面数的骰子"""
    return [random.randint(1, faces) for _ in range(count)]


def evaluate_expression(expr: str) -> int:
    """计算表达式（支持括号和基本运算）"""
    try:
        return eval(expr, {"__builtins__": {}})
    except:
        return None


@register("simple_dice", "evpeople", "一个简单的骰子", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法"""

    @filter.command("r")
    async def roll_dice(self, event: AstrMessageEvent):
        """投掷骰子
        支持格式:
        - /r 或 /掷骰 → 投掷 1d20
        - /r 2d6 → 投掷 2 个六面骰
        - /r d100 → 投掷百分骰 (0-100)
        - /r 3d10+5 → 3d10 + 5
        - /r 2d6-1d4+3 → 支持混合运算
        """
        message_str = event.message_str.strip()

        # 移除指令前缀，获取参数
        args = message_str
        for prefix in ["/r ", "/r"]:
            if message_str.startswith(prefix):
                args = message_str[len(prefix):].strip()
                break

        # 默认 1d20
        if not args:
            dice_expr = "1d20"
        else:
            dice_expr = args

        # 检查是否有括号表达式
        if "(" in dice_expr or ")" in dice_expr:
            # 直接计算整个表达式（支持复杂表达式）
            try:
                # 先替换所有 NdM 为随机结果
                def dice_replacer(match):
                    count = int(match.group(1)) if match.group(1) else 1
                    faces = int(match.group(2))
                    rolls = roll_dice(count, faces)
                    return str(sum(rolls))

                pattern = r'(\d*)d(\d+)'
                result_expr = re.sub(pattern, dice_replacer, dice_expr, flags=re.IGNORECASE)
                final_result = evaluate_expression(result_expr)

                if final_result is not None:
                    yield event.plain_result(f"掷骰结果: {final_result}")
                else:
                    yield event.plain_result(f"表达式解析失败，请检查格式")
            except Exception as e:
                logger.error(f"骰子表达式解析错误: {e}")
                yield event.plain_result(f"表达式解析失败: {str(e)}")
            return

        # 解析简单骰子表达式
        base_value, dice_parts, original_expr = parse_dice_expression(dice_expr)

        if not dice_parts:
            yield event.plain_result(f"无效的骰子格式: {dice_expr}\n请使用如: 2d6, 3d10+5, d20 等格式")
            return

        # 执行投骰
        all_rolls = []
        total = base_value

        for count, faces in dice_parts:
            rolls = roll_dice(count, faces)
            all_rolls.extend(rolls)
            roll_sum = sum(rolls)
            total += roll_sum

        # 构建结果消息
        if base_value != 0:
            dice_desc = " + ".join([f"{count}d{faces}" for count, faces in dice_parts])
            if len(all_rolls) <= 5:
                rolls_str = ", ".join(map(str, all_rolls))
                result_msg = f"掷骰 ({dice_desc}) + {base_value}: [{rolls_str}] + {base_value} = {total}"
            else:
                result_msg = f"掷骰 ({dice_desc}) + {base_value}: [{len(all_rolls)}个骰子] = {total}"
        else:
            if len(dice_parts) == 1:
                count, faces = dice_parts[0]
                if count == 1:
                    if len(all_rolls) == 1:
                        result_msg = f"掷骰 d{faces}: {all_rolls[0]}"
                    else:
                        result_msg = f"掷骰 {count}d{faces}: [{', '.join(map(str, all_rolls))}] = {total}"
                else:
                    result_msg = f"掷骰 {count}d{faces}: [{', '.join(map(str, all_rolls))}] = {total}"
            else:
                dice_desc = " + ".join([f"{count}d{faces}" for count, faces in dice_parts])
                if len(all_rolls) <= 5:
                    rolls_str = ", ".join(map(str, all_rolls))
                    result_msg = f"掷骰 {dice_desc}: [{rolls_str}] = {total}"
                else:
                    result_msg = f"掷骰 {dice_desc}: [{len(all_rolls)}个骰子] = {total}"

        yield event.plain_result(result_msg)

    @filter.command("kv")
    async def kv_command(self, event: AstrMessageEvent):
        """KV 存储命令，支持读取、写入、列出"""
        message_str = event.message_str.strip()

        # 解析参数
        parts = message_str.split(maxsplit=2)
        if len(parts) < 2:
            yield event.plain_result(
                "用法:\n"
                "/kv get <键名> - 读取值\n"
                "/kv set <键名> <值> - 设置单个值\n"
                "/kv set <属性值对> - 批量设置，如: 生命30 经验20\n"
                "/kv list [前缀] - 列出所有数据，可选按前缀过滤\n"
                "/kv del <键名> - 删除键"
            )
            return

        sub_cmd = parts[1].lower()

        if sub_cmd == "get":
            if len(parts) < 3:
                yield event.plain_result("用法: /kv get <键名>")
                return
            key = parts[2].strip()
            storage_id = self._get_storage_id("user", event)
            data = self._load_kv()
            storage = data.get(storage_id, {})
            if key not in storage:
                yield event.plain_result(f"键 '{key}' 不存在")
            else:
                yield event.plain_result(f"{key} = {storage[key]}")

        elif sub_cmd == "set":
            if len(parts) < 3:
                yield event.plain_result("用法: /kv set <键名> <值> 或 /kv set <属性值对>")
                return
            storage_id = self._get_storage_id("user", event)
            data = self._load_kv()
            if storage_id not in data:
                data[storage_id] = {}

            # 解析输入
            rest = parts[2] if len(parts) == 3 else " ".join(parts[2:])
            updates = self._parse_upsert_value(rest)

            # 如果解析结果是单个 "value" 键，说明是纯字符串或数字
            if updates == {"value": rest}:
                # 格式: /kv set key value
                if len(parts) < 4:
                    yield event.plain_result("用法: /kv set <键名> <值>")
                    return
                key = parts[2].strip()
                value = parts[3].strip()
                try:
                    if '.' in value:
                        parsed = float(value)
                    else:
                        parsed = int(value)
                except ValueError:
                    parsed = value
                data[storage_id][key] = parsed
                self._save_kv(data)
                yield event.plain_result(f"已保存: {key} = {parsed}")
            else:
                # 格式: /kv set 生命30经验20
                results = []
                for k, v in updates.items():
                    data[storage_id][k] = v
                    results.append(f"{k}={v}")
                self._save_kv(data)
                yield event.plain_result(f"已更新: {', '.join(results)}")

        if sub_cmd == "list":
            storage_id = self._get_storage_id("user", event)
            data = self._load_kv()
            storage = data.get(storage_id, {})

            # 支持前缀搜索
            prefix = None
            if len(parts) >= 3:
                prefix = parts[2].strip()
                storage = {k: v for k, v in storage.items() if k.startswith(prefix)}

            if not storage:
                if prefix:
                    yield event.plain_result(f"未找到前缀为 '{prefix}' 的键值对")
                else:
                    yield event.plain_result("当前无存储的数据")
            else:
                lines = [f"{k} = {v}" for k, v in storage.items()]
                yield event.plain_result("\n".join(lines))

        elif sub_cmd == "del":
            if len(parts) < 3:
                yield event.plain_result("用法: /kv del <键名>")
                return
            key = parts[2].strip()
            storage_id = self._get_storage_id("user", event)
            data = self._load_kv()
            storage = data.get(storage_id, {})
            if key in storage:
                del storage[key]
                self._save_kv(data)
                yield event.plain_result(f"已删除: {key}")
            else:
                yield event.plain_result(f"键 '{key}' 不存在")

        else:
            yield event.plain_result(f"未知子命令: {sub_cmd}\n可用: get, set, setmulti, list, del")

    def _get_storage_id(self, scope: str, event: AstrMessageEvent) -> str:
        """生成存储 ID"""
        if scope == "group":
            try:
                return f"group_{event.group_id}"
            except Exception:
                return f"group_unknown"
        else:
            try:
                return f"user_{event.user_id}"
            except Exception:
                return f"user_unknown"

    def _load_kv(self) -> Dict:
        """加载 KV 数据"""
        Path(_KV_FILE).parent.mkdir(exist_ok=True)
        if not Path(_KV_FILE).exists():
            return {}
        try:
            return json.loads(Path(_KV_FILE).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_kv(self, data: Dict):
        """保存 KV 数据"""
        Path(_KV_FILE).parent.mkdir(exist_ok=True)
        Path(_KV_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _parse_upsert_value(self, value: Any) -> Dict[str, Any]:
        """解析一行字符串形式的多个属性，如 "生命30经验20" """
        if isinstance(value, str):
            # 尝试解析 JSON
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

            # 解析 "属性名数值" 格式
            # 支持格式: "生命30经验20" -> {"生命": 30, "经验": 20}
            result = {}
            import re
            # 匹配中文字符 + 数字
            pattern = r'([\u4e00-\u9fff]+)(-?\d+(?:\.\d+)?)'
            matches = re.findall(pattern, value)
            for name, num in matches:
                result[name] = float(num) if '.' in num else int(num)
            if result:
                return result

            # 如果不是这种格式，作为普通值返回
            return {"value": value}
        return value if isinstance(value, dict) else {"value": value}

    @filter.llm_tool(name="kv_read")
    async def kv_read(
        self,
        event: AstrMessageEvent,
        key: str,
        scope: str = "user"
    ) -> str:
        '''读取指定键的值。

        Args:
            key(string): 要读取的键名
            scope(string): 作用域，"user" 或 "group"
        '''
        storage_id = self._get_storage_id(scope, event)
        data = self._load_kv()
        storage = data.get(storage_id, {})
        if key not in storage:
            return f"键 '{key}' 不存在"
        return str(storage[key])

    @filter.llm_tool(name="kv_upsert")
    async def kv_upsert(
        self,
        event: AstrMessageEvent,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        multi: Optional[str] = None,
        scope: str = "user"
    ) -> str:
        '''写入或更新键值对。支持单个键值或一次性更新多个属性。

        Args:
            key(string): 键名（单个键值模式）
            value(object): 值（单个键值模式，支持数字、字符串、列表、字典）
            multi(string): 一行字符串更新多个属性，如 "生命30经验20"
            scope(string): 作用域，"user" 或 "group"
        '''
        storage_id = self._get_storage_id(scope, event)
        data = self._load_kv()
        if storage_id not in data:
            data[storage_id] = {}

        results = []

        # 多属性模式
        if multi:
            updates = self._parse_upsert_value(multi)
            for k, v in updates.items():
                data[storage_id][k] = v
                results.append(f"{k}={v}")
            self._save_kv(data)
            return f"已更新: {', '.join(results)}"

        # 单键值模式
        if key is not None and value is not None:
            parsed_value = self._parse_upsert_value(value)
            if isinstance(parsed_value, dict) and "value" in parsed_value and key == "value":
                # 说明是普通字符串值
                data[storage_id]["value"] = parsed_value["value"]
            elif isinstance(parsed_value, dict) and key not in parsed_value:
                # value 是 dict，但 key 不是，存储整个 dict 到 key
                data[storage_id][key] = parsed_value
                results.append(f"{key}={parsed_value}")
            else:
                data[storage_id][key] = parsed_value
                results.append(f"{key}={parsed_value}")
            self._save_kv(data)
            return f"已保存: {', '.join(results)}"

        return "错误: 请提供 key 和 value，或使用 multi 参数"

    @filter.llm_tool(name="kv_list")
    async def kv_list(
        self,
        event: AstrMessageEvent,
        scope: str = "user",
        prefix: Optional[str] = None
    ) -> str:
        '''列出指定作用域下的所有键值对，可选按前缀过滤。

        Args:
            scope(string): 作用域，"user" 或 "group"
            prefix(string, optional): 键名前缀，仅返回以此前缀开头的键值对
        '''
        storage_id = self._get_storage_id(scope, event)
        data = self._load_kv()
        storage = data.get(storage_id, {})

        if prefix:
            filtered = {k: v for k, v in storage.items() if k.startswith(prefix)}
            if not filtered:
                return f"未找到前缀为 '{prefix}' 的键值对"
            return json.dumps(filtered, ensure_ascii=False, indent=2)

        if not storage:
            return f"当前无存储的数据"
        return json.dumps(storage, ensure_ascii=False, indent=2)

    @filter.llm_tool(name="roll_dice")
    async def llm_roll_dice(self, event: AstrMessageEvent, expression: str = "1d20", hidden: bool = False) -> str:
        '''投掷骰子，支持各种骰子表达式。LLM 在需要随机数或进行 RPG 掷骰时可以调用此工具。

        Args:
            expression(string): 骰子表达式，如 "1d20"、"2d6"、"3d10+5"、"d100" 等。默认为 "1d20"。支持在末尾添加 "+key" 格式来加上 KV 存储的值作为修正值，如 "1d20+str"。
            hidden(boolean): 是否暗投。True 表示暗投，只显示"进行了一次暗投"；False 表示明投，显示具体结果。默认为 False。
        '''
        dice_expr = expression.strip() if expression else "1d20"

        # 检测是否有 +key 后缀
        modifier_key = None
        if "+" in dice_expr:
            parts = dice_expr.rsplit("+", 1)
            if len(parts) == 2 and parts[1].isalpha():
                potential_key = parts[1]
                # 检查这个后缀是否是有效的字母（不是纯数字）
                if not potential_key.isdigit():
                    dice_expr = parts[0]
                    modifier_key = potential_key

        # 获取 KV 修正值
        modifier_value = 0
        modifier_source = ""
        if modifier_key:
            storage_id = self._get_storage_id("user", event)
            data = self._load_kv()
            storage = data.get(storage_id, {})
            if modifier_key in storage:
                try:
                    modifier_value = float(storage[modifier_key])
                    modifier_source = f"+{modifier_key}({modifier_value})"
                except (ValueError, TypeError):
                    modifier_source = ""
                    modifier_key = None

        # 检查是否有括号表达式
        if "(" in dice_expr or ")" in dice_expr:
            try:
                def dice_replacer(match):
                    count = int(match.group(1)) if match.group(1) else 1
                    faces = int(match.group(2))
                    rolls = roll_dice(count, faces)
                    return str(sum(rolls))

                pattern = r'(\d*)d(\d+)'
                result_expr = re.sub(pattern, dice_replacer, dice_expr, flags=re.IGNORECASE)
                final_result = evaluate_expression(result_expr)

                if final_result is not None:
                    final_total = final_result + modifier_value
                    if modifier_key and modifier_value != 0:
                        result_msg = f"掷骰结果: {final_result}{modifier_source} = {final_total}"
                    else:
                        result_msg = f"掷骰结果: {final_result}"
                    if hidden:
                        event.set_result(MessageEventResult(chain=[Comp.Plain("进行了一次暗投")]))
                        return result_msg
                    event.set_result(MessageEventResult(chain=[Comp.Plain(result_msg)]))
                    return result_msg
                else:
                    error_msg = "表达式解析失败，请检查格式。支持格式: 1d20, 2d6, 3d10+5, (2d6+1d8)*2 等"
                    event.set_result(MessageEventResult(chain=[Comp.Plain(error_msg)]))
                    return error_msg
            except Exception as e:
                logger.error(f"骰子表达式解析错误: {e}")
                error_msg = f"表达式解析失败: {str(e)}，请检查格式。支持格式: 1d20, 2d6, 3d10+5, (2d6+1d8)*2 等"
                event.set_result(MessageEventResult(chain=[Comp.Plain(error_msg)]))
                return error_msg

        # 解析简单骰子表达式
        base_value, dice_parts, _ = parse_dice_expression(dice_expr)

        if not dice_parts:
            error_msg = f"无效的骰子格式: {dice_expr}，请使用如: 2d6, 3d10+5, d20 等格式"
            event.set_result(MessageEventResult(chain=[Comp.Plain(error_msg)]))
            return error_msg

        # 执行投骰
        all_rolls = []
        total = base_value

        for count, faces in dice_parts:
            rolls = roll_dice(count, faces)
            all_rolls.extend(rolls)
            total += sum(rolls)

        # 加上 KV 修正值
        if modifier_key and modifier_value != 0:
            final_total = total + modifier_value
            if len(all_rolls) <= 5:
                rolls_str = ", ".join(map(str, all_rolls))
                if base_value != 0:
                    result_msg = f"掷骰 {dice_expr}: [{rolls_str}] + {base_value}{modifier_source} = {total} + {modifier_value} = {final_total}"
                else:
                    result_msg = f"掷骰 {dice_expr}: [{rolls_str}]{modifier_source} = {total} + {modifier_value} = {final_total}"
            else:
                if base_value != 0:
                    result_msg = f"掷骰 {dice_expr}: [{len(all_rolls)}个骰子] + {base_value}{modifier_source} = {total} + {modifier_value} = {final_total}"
                else:
                    result_msg = f"掷骰 {dice_expr}: [{len(all_rolls)}个骰子]{modifier_source} = {total} + {modifier_value} = {final_total}"
        else:
            if len(all_rolls) <= 5:
                rolls_str = ", ".join(map(str, all_rolls))
                if base_value != 0:
                    result_msg = f"掷骰 {dice_expr}: [{rolls_str}] + {base_value} = {total}"
                else:
                    result_msg = f"掷骰 {dice_expr}: [{rolls_str}] = {total}"
            else:
                if base_value != 0:
                    result_msg = f"掷骰 {dice_expr}: [{len(all_rolls)}个骰子] + {base_value} = {total}"
                else:
                    result_msg = f"掷骰 {dice_expr}: [{len(all_rolls)}个骰子] = {total}"

        if hidden:
            event.set_result(MessageEventResult(chain=[Comp.Plain("进行了一次暗投")]))
            return result_msg
        event.set_result(MessageEventResult(chain=[Comp.Plain(result_msg)]))
        return result_msg

    async def terminate(self):
        """可选择实现异步的插件销毁方法"""
