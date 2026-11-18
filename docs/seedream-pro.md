# Seedream 5.0 Pro 官方接入

提供方为 `volcengine`，模型为 `doubao-seedream-5-0-pro-260628`，调用官方 Ark `/api/v3/images/generations`，复用 `ARK_API_KEY`，无需 Krene 或第三方推理服务。

## 使用

在 API 生成节点选择火山引擎及上述模型，可切换普通生图/参考图编辑和图像分层。标注图、草图等作为参考图连接，编辑要求写入提示词。

- 普通模式：1K、1.5K、2K 或自定义宽高；最多 10 张参考图；1–8 次独立请求。
- 分层：恰好一张参考图；一次一组；提示词留空为自动分层，填写提示词可指定元素；支持 auto 或上述预设尺寸。
- 通用设置：PNG/JPEG、URL/Base64 返回、标准/快速提示词优化、水印。
- 透明背景编辑：单张有透明像素的参考图，PNG 输出；适合再次编辑分层结果。

输出保存到本地，保留名称、描述、z_index 和 bounding_box。分层输出节点提供预览、ZIP、PSD 链接。ZIP 包含原始透明 PNG、坐标清单、可切换图层的 HTML 预览与 PSD；需要缩放的图层额外保存 aligned PNG，原始文件不覆盖。PSD 按官方边界框对齐，写入 Unicode 名称并回读检查像素、坐标和名称。

生图会计入官方调用用量；应用不会为此模式启用跨平台补满。未将其他版本的流式输出、组图、联网工具参数套用到 Pro。参数被官方拒绝时保留真实错误，不自动付费重复生成。

## 本次验证（2026-09-21）

- 13 项 Python 测试与 3 项 Node 测试通过，JavaScript 语法检查通过。
- 浏览器实测：原始角色自动分层返回底图 + 7 个透明图层，1116×2000 基准画布。
- 官方任务：`canvas_img_733806a66fe140b887af642a75f93ef8`，实际约 74 秒。
- 此前正面重绘图的指定部件分层被上游以 image InvalidParameter 拒绝，未把该尝试标记成功。
- 成功结果的中文图层名导出异常已修复；直接用缓存图层恢复导出，没有重新调用模型。
- 示例画布：`bb7eadbbf83a4b40a5dc1631ea35eb06`，新版服务在本机 3002 端口；旧 3001 进程仍需重启加载代码。
- 自动分层没有拆出独立眼睛、嘴和发束，不能等同于完成 Live2D 拆件或绑定。

## 开发验证

```powershell
.\python\python.exe -m pytest tests/test_seedream_pro.py tests/test_volcengine_image_auth.py -q
node --test tests/seedream-pro.test.cjs
node --check static/js/canvas.js
node --check static/js/seedream-pro.js
```

官方依据：[Seedream 产品页](https://seed.bytedance.com/en/seedream5_0_pro)、[官方 SDK 请求实现](https://github.com/volcengine/volcengine-python-sdk/blob/master/volcenginesdkarkruntime/resources/images/images.py)、[官方响应类型](https://github.com/volcengine/volcengine-python-sdk/blob/master/volcenginesdkarkruntime/types/images/images.py)。
