# NovelAI V5 接入

平台：`NovelAI V5`，本机平台 ID：`custom-api-8`，协议：`novelai`。

- 官方地址：`https://image.novelai.net`。
- 模型：`nai-diffusion-5-full`、`nai-diffusion-5-curated`。
- Token 已通过画布设置保存于本机 `API/.env` 的 `API_PROVIDER_CUSTOM_API_8_KEY`；不复制到文档、源码或日志。
- 官方生成接口：`POST /ai/generate-image`，Bearer 认证；ZIP 中的 PNG 会解析并交给画布现有图片保存流程。
- 「验证地址」「验证协议」「拉取模型」只请求 `GET /user/data`，显示账户余额；返回的 V5 模型列表为接入预设，不代表逐个模型已经实测出图。

## 使用

刷新无限画布，在 API 生图节点选择 `NovelAI V5` 和 V5 Full 或 V5 Curated，输入提示词后生成。

第一版支持文字生图，固定 23 步、引导 7、Euler Ancestral、Karras，单次请求一张；数量由画布顺序调度。标准尺寸限制在 1,048,576 像素内，宽高按 64 像素对齐；自定义尺寸原样发送、校验不合规则拒绝。质量档位和自动换平台补满在该节点停用。

参考图、Vibe Transfer、Precise Reference、局部重绘暂未接入；有参考图时明确报错，不会悄悄忽略。

## 验证与限制

已做真实 Token 认证和余额检查，另用模拟官方响应测试请求构造、PNG/ZIP 解析、画布分发和错误处理。没有提交真实付费生成任务，因此实际出图仍待首次生成验证。

当前官方 `request-price` 路径返回 404，未将本地估算伪装成官方报价。生成发生网络中断或服务器错误时不自动重试，以免重复扣点。

本次按用户指令覆盖了旧 Persistent API Token；旧工具如仍使用旧 Token，需要自行更新为本机保存的新 Token。
