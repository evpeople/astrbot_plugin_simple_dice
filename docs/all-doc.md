最小实例
插件模版中的 main.py 是一个最小的插件实例。


from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger # 使用 astrbot 提供的 logger 接口

@register("helloworld", "author", "一个简单的 Hello World 插件", "1.0.0", "repo url")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        '''这是一个 hello world 指令''' # 这是 handler 的描述，将会被解析方便用户了解插件内容。非常建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 获取消息的纯文本内容
        logger.info("触发hello world指令!")
        yield event.plain_result(f"Hello, {user_name}!") # 发送一条纯文本消息

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''
解释如下：

插件需要继承 Star 类。
Context 类用于插件与 AstrBot Core 交互，可以由此调用 AstrBot Core 提供的各种 API。
具体的处理函数 Handler 在插件类中定义，如这里的 helloworld 函数。
AstrMessageEvent 是 AstrBot 的消息事件对象，存储了消息发送者、消息内容等信息。
AstrBotMessage 是 AstrBot 的消息对象，存储了消息平台下发的消息的具体内容。可以通过 event.message_obj 获取。
TIP

Handler 一定需要在插件类中注册，前两个参数必须为 self 和 event。如果文件行数过长，可以将服务写在外部，然后在 Handler 中调用。

插件类所在的文件名需要命名为 main.py。

所有的处理函数都需写在插件类中。为了精简内容，在之后的章节中，我们可能会忽略插件类的定义。


处理消息事件
事件监听器可以收到平台下发的消息内容，可以实现指令、指令组、事件监听等功能。

事件监听器的注册器在 astrbot.api.event.filter 下，需要先导入。请务必导入，否则会和 python 的高阶函数 filter 冲突。


from astrbot.api.event import filter, AstrMessageEvent
消息与事件
AstrBot 接收消息平台下发的消息，并将其封装为 AstrMessageEvent 对象，传递给插件进行处理。

message-event

消息事件
AstrMessageEvent 是 AstrBot 的消息事件对象，其中存储了消息发送者、消息内容等信息。

消息对象
AstrBotMessage 是 AstrBot 的消息对象，其中存储了消息平台下发的消息具体内容，AstrMessageEvent 对象中包含一个 message_obj 属性用于获取该消息对象。


class AstrBotMessage:
    '''AstrBot 的消息对象'''
    type: MessageType  # 消息类型
    self_id: str  # 机器人的识别id
    session_id: str  # 会话id。取决于 unique_session 的设置。
    message_id: str  # 消息id
    group_id: str = "" # 群组id，如果为私聊，则为空
    sender: MessageMember  # 发送者
    message: List[BaseMessageComponent]  # 消息链。比如 [Plain("Hello"), At(qq=123456)]
    message_str: str  # 最直观的纯文本消息字符串，将消息链中的 Plain 消息（文本消息）连接起来
    raw_message: object
    timestamp: int  # 消息时间戳
其中，raw_message 是消息平台适配器的原始消息对象。

消息链
message-chain

消息链描述一个消息的结构，是一个有序列表，列表中每一个元素称为消息段。

常见的消息段类型有：

Plain：文本消息段
At：提及消息段
Image：图片消息段
Record：语音消息段
Video：视频消息段
File：文件消息段
大多数消息平台都支持上面的消息段类型。

此外，OneBot v11 平台（QQ 个人号等）还支持以下较为常见的消息段类型：

Face：表情消息段
Node：合并转发消息中的一个节点
Nodes：合并转发消息中的多个节点
Poke：戳一戳消息段
在 AstrBot 中，消息链表示为 List[BaseMessageComponent] 类型的列表。

指令
message-event-simple-command


from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

@register("helloworld", "Soulter", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("helloworld") # from astrbot.api.event.filter import command
    async def helloworld(self, event: AstrMessageEvent):
        '''这是 hello world 指令'''
        user_name = event.get_sender_name()
        message_str = event.message_str # 获取消息的纯文本内容
        yield event.plain_result(f"Hello, {user_name}!")
TIP

指令不能带空格，否则 AstrBot 会将其解析到第二个参数。可以使用下面的指令组功能，或者也使用监听器自己解析消息内容。

带参指令
command-with-param

AstrBot 会自动帮你解析指令的参数。


@filter.command("add")
def add(self, event: AstrMessageEvent, a: int, b: int):
    # /add 1 2 -> 结果是: 3
    yield event.plain_result(f"Wow! The anwser is {a + b}!")
指令组
指令组可以帮助你组织指令。


@filter.command_group("math")
def math(self):
    pass

@math.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    # /math add 1 2 -> 结果是: 3
    yield event.plain_result(f"结果是: {a + b}")

@math.command("sub")
async def sub(self, event: AstrMessageEvent, a: int, b: int):
    # /math sub 1 2 -> 结果是: -1
    yield event.plain_result(f"结果是: {a - b}")
指令组函数内不需要实现任何函数，请直接 pass 或者添加函数内注释。指令组的子指令使用 指令组名.command 来注册。

当用户没有输入子指令时，会报错并，并渲染出该指令组的树形结构。

image

image

image

理论上，指令组可以无限嵌套！


'''
math
├── calc
│   ├── add (a(int),b(int),)
│   ├── sub (a(int),b(int),)
│   ├── help (无参数指令)
'''

@filter.command_group("math")
def math():
    pass

@math.group("calc") # 请注意，这里是 group，而不是 command_group
def calc():
    pass

@calc.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"结果是: {a + b}")

@calc.command("sub")
async def sub(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"结果是: {a - b}")

@calc.command("help")
def calc_help(self, event: AstrMessageEvent):
    # /math calc help
    yield event.plain_result("这是一个计算器插件，拥有 add, sub 指令。")
指令别名
v3.4.28 后

可以为指令或指令组添加不同的别名：


@filter.command("help", alias={'帮助', 'helpme'})
def help(self, event: AstrMessageEvent):
    yield event.plain_result("这是一个计算器插件，拥有 add, sub 指令。")
事件类型过滤
接收所有
这将接收所有的事件。


@filter.event_message_type(filter.EventMessageType.ALL)
async def on_all_message(self, event: AstrMessageEvent):
    yield event.plain_result("收到了一条消息。")
群聊和私聊

@filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
async def on_private_message(self, event: AstrMessageEvent):
    message_str = event.message_str # 获取消息的纯文本内容
    yield event.plain_result("收到了一条私聊消息。")
EventMessageType 是一个 Enum 类型，包含了所有的事件类型。当前的事件类型有 PRIVATE_MESSAGE 和 GROUP_MESSAGE。

消息平台

@filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP | filter.PlatformAdapterType.QQOFFICIAL)
async def on_aiocqhttp(self, event: AstrMessageEvent):
    '''只接收 AIOCQHTTP 和 QQOFFICIAL 的消息'''
    yield event.plain_result("收到了一条信息")
当前版本下，PlatformAdapterType 有 AIOCQHTTP, QQOFFICIAL, GEWECHAT, ALL。

管理员指令

@filter.permission_type(filter.PermissionType.ADMIN)
@filter.command("test")
async def test(self, event: AstrMessageEvent):
    pass
仅管理员才能使用 test 指令。

多个过滤器
支持同时使用多个过滤器，只需要在函数上添加多个装饰器即可。过滤器使用 AND 逻辑。也就是说，只有所有的过滤器都通过了，才会执行函数。


@filter.command("helloworld")
@filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
async def helloworld(self, event: AstrMessageEvent):
    yield event.plain_result("你好！")
事件钩子
TIP

事件钩子不支持与上面的 @filter.command, @filter.command_group, @filter.event_message_type, @filter.platform_adapter_type, @filter.permission_type 一起使用。

Bot 初始化完成时
v3.4.34 后


from astrbot.api.event import filter, AstrMessageEvent

@filter.on_astrbot_loaded()
async def on_astrbot_loaded(self):
    print("AstrBot 初始化完成")
等待 LLM 请求时
在 AstrBot 准备调用 LLM 但还未获取会话锁时，会触发 on_waiting_llm_request 钩子。

这个钩子适合用于发送"正在等待请求..."等用户反馈提示，亦或是在锁外及时获取LLM请求而不用等到锁被释放。


from astrbot.api.event import filter, AstrMessageEvent

@filter.on_waiting_llm_request()
async def on_waiting_llm(self, event: AstrMessageEvent):
    await event.send("🤔 正在等待请求...")
这里不能使用 yield 来发送消息。如需发送，请直接使用 event.send() 方法。

LLM 请求时
在 AstrBot 默认的执行流程中，在调用 LLM 前，会触发 on_llm_request 钩子。

可以获取到 ProviderRequest 对象，可以对其进行修改。

ProviderRequest 对象包含了 LLM 请求的所有信息，包括请求的文本、系统提示等。


from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest

@filter.on_llm_request()
async def my_custom_hook_1(self, event: AstrMessageEvent, req: ProviderRequest): # 请注意有三个参数
    print(req) # 打印请求的文本
    req.system_prompt += "自定义 system_prompt"
这里不能使用 yield 来发送消息。如需发送，请直接使用 event.send() 方法。

LLM 请求完成时
在 LLM 请求完成后，会触发 on_llm_response 钩子。

可以获取到 ProviderResponse 对象，可以对其进行修改。


from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import LLMResponse

@filter.on_llm_response()
async def on_llm_resp(self, event: AstrMessageEvent, resp: LLMResponse): # 请注意有三个参数
    print(resp)
这里不能使用 yield 来发送消息。如需发送，请直接使用 event.send() 方法。

发送消息前
在发送消息前，会触发 on_decorating_result 钩子。

可以在这里实现一些消息的装饰，比如转语音、转图片、加前缀等等


from astrbot.api.event import filter, AstrMessageEvent

@filter.on_decorating_result()
async def on_decorating_result(self, event: AstrMessageEvent):
    result = event.get_result()
    chain = result.chain
    print(chain) # 打印消息链
    chain.append(Plain("!")) # 在消息链的最后添加一个感叹号
这里不能使用 yield 来发送消息。这个钩子只是用来装饰 event.get_result().chain 的。如需发送，请直接使用 event.send() 方法。

发送消息后
在发送消息给消息平台后，会触发 after_message_sent 钩子。


from astrbot.api.event import filter, AstrMessageEvent

@filter.after_message_sent()
async def after_message_sent(self, event: AstrMessageEvent):
    pass
这里不能使用 yield 来发送消息。如需发送，请直接使用 event.send() 方法。

优先级
指令、事件监听器、事件钩子可以设置优先级，先于其他指令、监听器、钩子执行。默认优先级是 0。


@filter.command("helloworld", priority=1)
async def helloworld(self, event: AstrMessageEvent):
    yield event.plain_result("Hello!")
控制事件传播

@filter.command("check_ok")
async def check_ok(self, event: AstrMessageEvent):
    ok = self.check() # 自己的逻辑
    if not ok:
        yield event.plain_result("检查失败")
        event.stop_event() # 停止事件传播
当事件停止传播，后续所有步骤将不会被执行。

假设有一个插件 A，A 终止事件传播之后所有后续操作都不会执行，比如执行其它插件的 handler、请求 LLM。



被动消息
被动消息指的是机器人被动回复消息。


@filter.command("helloworld")
async def helloworld(self, event: AstrMessageEvent):
    yield event.plain_result("Hello!")
    yield event.plain_result("你好！")

    yield event.image_result("path/to/image.jpg") # 发送图片
    yield event.image_result("https://example.com/image.jpg") # 发送 URL 图片，务必以 http 或 https 开头
主动消息
主动消息指的是机器人主动推送消息。某些平台可能不支持主动消息发送。

如果是一些定时任务或者不想立即发送消息，可以使用 event.unified_msg_origin 得到一个字符串并将其存储，然后在想发送消息的时候使用 self.context.send_message(unified_msg_origin, chains) 来发送消息。


from astrbot.api.event import MessageChain

@filter.command("helloworld")
async def helloworld(self, event: AstrMessageEvent):
    umo = event.unified_msg_origin
    message_chain = MessageChain().message("Hello!").file_image("path/to/image.jpg")
    await self.context.send_message(event.unified_msg_origin, message_chain)
通过这个特性，你可以将 unified_msg_origin 存储起来，然后在需要的时候发送消息。

TIP

关于 unified_msg_origin。 unified_msg_origin 是一个字符串，记录了一个会话的唯一 ID，AstrBot 能够据此找到属于哪个消息平台的哪个会话。这样就能够实现在 send_message 的时候，发送消息到正确的会话。有关 MessageChain，请参见接下来的一节。

富媒体消息
AstrBot 支持发送富媒体消息，比如图片、语音、视频等。使用 MessageChain 来构建消息。


import astrbot.api.message_components as Comp

@filter.command("helloworld")
async def helloworld(self, event: AstrMessageEvent):
    chain = [
        Comp.At(qq=event.get_sender_id()), # At 消息发送者
        Comp.Plain("来看这个图："),
        Comp.Image.fromURL("https://example.com/image.jpg"), # 从 URL 发送图片
        Comp.Image.fromFileSystem("path/to/image.jpg"), # 从本地文件目录发送图片
        Comp.Plain("这是一个图片。")
    ]
    yield event.chain_result(chain)
上面构建了一个 message chain，也就是消息链，最终会发送一条包含了图片和文字的消息，并且保留顺序。

TIP

在 aiocqhttp 消息适配器中，对于 plain 类型的消息，在发送中会使用 strip() 方法去除空格及换行符，可以在消息前后添加零宽空格 \u200b 以解决这个问题。

类似地，

文件 File


Comp.File(file="path/to/file.txt", name="file.txt") # 部分平台不支持
语音 Record


path = "path/to/record.wav" # 暂时只接受 wav 格式，其他格式请自行转换
Comp.Record(file=path, url=path)
视频 Video


path = "path/to/video.mp4"
Comp.Video.fromFileSystem(path=path)
Comp.Video.fromURL(url="https://example.com/video.mp4")
发送视频消息

from astrbot.api.event import filter, AstrMessageEvent

@filter.command("test")
async def test(self, event: AstrMessageEvent):
    from astrbot.api.message_components import Video
    # fromFileSystem 需要用户的协议端和机器人端处于一个系统中。
    music = Video.fromFileSystem(
        path="test.mp4"
    )
    # 更通用
    music = Video.fromURL(
        url="https://example.com/video.mp4"
    )
    yield event.chain_result([music])
发送视频消息

发送群合并转发消息
大多数平台都不支持此种消息类型，当前适配情况：OneBot v11

可以按照如下方式发送群合并转发消息。


from astrbot.api.event import filter, AstrMessageEvent

@filter.command("test")
async def test(self, event: AstrMessageEvent):
    from astrbot.api.message_components import Node, Plain, Image
    node = Node(
        uin=905617992,
        name="Soulter",
        content=[
            Plain("hi"),
            Image.fromFileSystem("test.jpg")
        ]
    )
    yield event.chain_result([node])




