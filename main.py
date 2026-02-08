import re
import random
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp


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

    @filter.llm_tool(name="roll_dice")
    async def llm_roll_dice(self, event: AstrMessageEvent, expression: str = "1d20", hidden: bool = False) -> str:
        '''投掷骰子，支持各种骰子表达式。LLM 在需要随机数或进行 RPG 掷骰时可以调用此工具。

        Args:
            expression(string): 骰子表达式，如 "1d20"、"2d6"、"3d10+5"、"d100" 等。默认为 "1d20"。
            hidden(bool): 是否暗投。True 表示暗投，只显示"进行了一次暗投"；False 表示明投，显示具体结果。默认为 False。
        '''
        dice_expr = expression.strip() if expression else "1d20"

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
                    result_msg = f"掷骰结果: {final_result}"
                    if hidden:
                        await event.send(event.chain_result([Comp.Plain("进行了一次暗投")]))
                    else:
                        await event.send(event.chain_result([Comp.Plain(result_msg)]))
                    event.set_result(MessageEventResult(chain=[Comp.Plain(result_msg)]))
                else:
                    error_msg = "表达式解析失败，请检查格式。支持格式: 1d20, 2d6, 3d10+5, (2d6+1d8)*2 等"
                    await event.send(event.chain_result([Comp.Plain(error_msg)]))
                    event.set_result(MessageEventResult(chain=[Comp.Plain(error_msg)]))
            except Exception as e:
                logger.error(f"骰子表达式解析错误: {e}")
                error_msg = f"表达式解析失败: {str(e)}，请检查格式。支持格式: 1d20, 2d6, 3d10+5, (2d6+1d8)*2 等"
                await event.send(event.chain_result([Comp.Plain(error_msg)]))
                event.set_result(MessageEventResult(chain=[Comp.Plain(error_msg)]))
            return

        # 解析简单骰子表达式
        base_value, dice_parts, _ = parse_dice_expression(dice_expr)

        if not dice_parts:
            error_msg = f"无效的骰子格式: {dice_expr}，请使用如: 2d6, 3d10+5, d20 等格式"
            await event.send(event.chain_result([Comp.Plain(error_msg)]))
            event.set_result(MessageEventResult(chain=[Comp.Plain(error_msg)]))
            return

        # 执行投骰
        all_rolls = []
        total = base_value

        for count, faces in dice_parts:
            rolls = roll_dice(count, faces)
            all_rolls.extend(rolls)
            total += sum(rolls)

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
            await event.send(event.chain_result([Comp.Plain("进行了一次暗投")]))
        else:
            await event.send(event.chain_result([Comp.Plain(result_msg)]))
        event.set_result(MessageEventResult(chain=[Comp.Plain(result_msg)]))

    async def terminate(self):
        """可选择实现异步的插件销毁方法"""
