# AutoDL H3 画布视频生成接入设计

日期：2026-08-24

## 1. 目标

在 Infinite Canvas 现有“视频生成”节点中加入 AutoDL.Art provider，并把 AutoDL 设为新建视频节点的默认平台。节点默认使用“自动选择”模式，根据提示词、时长、图片、音频和首尾帧设置选择正确的 MiniMax H3 工作流。

接入必须继续复用现有画布结构：

```text
[ Group：提示词 + 参考素材 ] -> [ 视频生成 ] -> [ Output ]
```

生成任务必须真实从视频节点发起，任务状态、AutoDL task ID、实际工作流、选择原因和本地视频结果都保留在画布中。不能使用标准 ComfyUI `/prompt`、`/history` 或 `/view` 接口替代 AutoDL 包装 API。

## 2. 范围

### 2.1 本次包含

- 新建视频节点默认平台为 `AutoDL`。
- 工作流选择默认值为 `自动选择`，空节点的初始候选为 `minimax_h3_lightx2v_v5`。
- 接入 AutoDL 当前公开的 7 个 MiniMax H3 视频工作流。
- 根据输入自动解析工作流，并允许用户手动覆盖。
- 根据工作流动态约束图片、音频、时长、比例和分辨率。
- 使用 AutoDL 原生异步提交/查询协议。
- 保存 task ID，支持页面刷新后继续查询原任务。
- 成功后立即把短期结果下载到本地 `output`，再写入连接的 Output 节点。
- 对 AutoDL Token、任务错误、本地素材公网可达性和重复付费风险做明确处理。
- 保留现有火山引擎、RunningHub、APIMart、即梦及其他视频 provider 行为。

### 2.2 本次不包含

- 任意 AutoDL ComfyUI 工作流 JSON 编辑器。
- 自动发现并无审核地接入未来新增工作流。
- 把本地参考视频转成图片序列或自动抽首尾帧。
- 视频拼接、补帧、失败后自动重试或自动再付费生成。
- 修改已经保存的旧视频节点平台或模型。
- 把用户本地素材在无明确操作的情况下上传到第三方临时文件服务。

## 3. 当前项目适配点

当前前端视频节点位于 `static/js/canvas.js`：

- `videoApiProviders()` 和 `providerVideoModels()` 提供平台及模型选项。
- `renderVideoBody()` 渲染平台、模型、时长、比例、分辨率与功能开关。
- `runVideoNode()` 收集 Group 输入并提交 `/api/canvas-video`。
- Output 已支持视频展示、下载、帧截取和运行元数据。

当前后端位于 `main.py`：

- `CanvasVideoRequest` 是统一视频请求模型。
- `/api/canvas-video` 按 provider 分流。
- `save_remote_video_to_output()` 已能把远程视频保存到本地输出目录。
- `data/api_providers.json` 保存平台配置，但密钥由后端安全配置管理。
- 画布文档保存在 `data/canvases/<canvas_id>.json`。

本地服务地址为 `http://127.0.0.1:3001`。实现时保留用户当前未提交的 `static/canvas.html` 修改，不覆盖无关工作。

## 4. AutoDL API 约束

### 4.1 认证与端点

认证头：

```text
Authorization: <ComfyUI group token>
Content-Type: application/json
```

Token 不带 `Bearer` 前缀。后端按固定顺序寻找安全配置：进程环境中的 `AUTODL_TOKEN`、项目目录及其父目录中的 `.env.autodl`、最后是 `%USERPROFILE%/.codex/secrets/autodl.env`。不得把 Token 写入 provider JSON、画布 JSON、请求元数据、控制台日志或错误正文。

提交：

```text
POST https://autodl.art/api/v1/comfyui/comfyui_workflow/{workflow_id}
```

查询：

```text
GET https://autodl.art/api/v1/comfyui/comfyui_workflow/result/{task_id}
```

`QUEUED` 和 `RUNNING` 都是非终态；`SUCCESS` 为成功；`FAILED` 为失败。成功结果 URL 有效期短，必须立即下载。

### 4.2 固定工作流注册表

实现使用经过 AutoDL“在线调用 API”面板核对的固定注册表。前端显示安全元数据，后端保存完整、权威的字段映射。

| 工作流 ID | UI 名称 | 时长 | 图片 | 音频 | 分辨率 |
|---|---|---:|---:|---:|---|
| `minimax_h3_lightx2v_v5` | H3 多图参考生视频 | 1–10 秒 | 1–9 | 0 | 480p/768p/1080p，横/竖/1:1 |
| `minimax_h3_lightx2v_v5_15s` | H3 多图生视频 15 秒 | 1–15 秒 | 1–9 | 0 | 480p/768p，横/竖/1:1 |
| `minimax_h3_lightx2v_no_pic` | H3 文生视频 | 1–15 秒 | 0 | 0 | 480p/768p，横/竖 |
| `minimax_h3_lightx2v` | H3 首尾帧视频 | 1–15 秒 | 正好 2 | 0 | 480p/768p，横/竖 |
| `minimax_h3_image_audio_to_video_v2` | H3 多图多音频生视频 | 1–10 秒 | 0–9 | 0–3 | 480p/768p/1080p，横/竖 |
| `minimax_h3_image_audio_to_video_v2_15s` | H3 多图多音频生视频 15 秒 | 1–15 秒 | 0–9 | 0–3 | 480p/768p，横/竖 |
| `minimax_h3_image_audio_to_video` | H3 自动对口型 | 1–15 秒 | 正好 1 | 正好 1 | 480p/768p/1080p，横/竖 |

准确请求字段如下：

- 多图：`prompt`、`duration`、`resolution`、可选 `seed`、`ref_image_0` 至 `ref_image_8`。
- 文生视频：`prompt`、`duration`、`resolution`。
- 首尾帧：`prompt`、`duration`、`resolution`、`first_frame`、`last_frame`。
- 多图多音频：`prompt`、`duration`、`resolution`、可选 `seed`、`ref_image_0` 至 `ref_image_8`、`ref_audio_0` 至 `ref_audio_2`。
- 自动对口型：`resolution`、`ref_image_0`、`ref_audio_0`、`audio_duration`。提示词只参与自动路由，不发送到不支持 `prompt` 的对口型工作流。

不得为工作流增加在线面板没有声明的字段，也不得猜测字段名。

## 5. 自动路由设计

### 5.1 节点状态

视频节点新增以下持久字段：

```json
{
  "apiProvider": "autodl",
  "workflowMode": "auto",
  "workflowId": "",
  "resolvedWorkflowId": "minimax_h3_lightx2v_v5",
  "resolvedWorkflowReason": "默认多图参考工作流"
}
```

- `workflowMode` 为 `auto` 或 `manual`。
- 自动模式下，`workflowId` 留空，`resolvedWorkflowId` 是当前预览结果。
- 手动模式下，`workflowId` 保存用户选择，后端仍验证输入是否兼容。
- 旧节点没有这些字段时保持原 provider，不迁移到 AutoDL。

### 5.2 路由优先级

后端解析器是权威实现；前端使用同一注册表元数据给出即时预览。运行时以后端结果为准。

解析顺序：

1. 手动模式：使用用户指定工作流，然后执行严格校验。
2. 存在参考视频：返回不支持错误，不提交任务。
3. 图片超过 9 张或音频超过 3 段：返回输入超限错误。
4. 正好 1 张图片和 1 段音频，且提示词含对口型意图：选择 `minimax_h3_image_audio_to_video`。
5. 存在音频：时长 1–10 秒选择 `minimax_h3_image_audio_to_video_v2`；11–15 秒选择 `minimax_h3_image_audio_to_video_v2_15s`。
6. 开启首尾帧：必须正好 2 张图片，选择 `minimax_h3_lightx2v`。
7. 存在图片：时长 1–10 秒选择 `minimax_h3_lightx2v_v5`；11–15 秒选择 `minimax_h3_lightx2v_v5_15s`。
8. 只有提示词：选择 `minimax_h3_lightx2v_no_pic`。
9. 空节点：仅显示 `minimax_h3_lightx2v_v5` 为初始候选；运行时仍因缺少提示词和必填图片而被拦截。

对口型意图匹配中英文关键词，包括：`对口型`、`口型`、`嘴型`、`说话`、`讲话`、`念台词`、`配音`、`唱歌`、`演唱`、`lip sync`、`lipsync`、`speaking`、`talking`、`singing`。匹配只用于选择工作流，不改写用户提示词。

### 5.3 自动选择说明

节点在工作流选择器下显示：

```text
自动选择：H3 多图生视频 15 秒
原因：连接了 3 张图片，时长 12 秒，无音频
```

素材数量、顺序、时长、首尾帧开关或提示词变化时更新说明。已经提交的任务使用运行快照，不因后续编辑而改变。

## 6. UI 设计

继续使用现有视频节点布局，不新增独立 AutoDL 节点。

### 6.1 平台与工作流

- 平台下拉框加入内置 `AutoDL`，并作为新节点默认值。
- 原“模型”下拉框在 AutoDL 下显示为“工作流”。
- 第一项为“自动选择”，后续列出 7 个固定工作流的友好名称。
- 手动选择具体工作流后进入手动模式；重新选择“自动选择”恢复自动模式。

### 6.2 动态控件

- 文生视频隐藏图片必填提示。
- 首尾帧模式把第 1、2 张图片分别标为首帧、尾帧。
- 多图工作流显示图片数量 `N/9`。
- 音频工作流显示音频数量 `N/3`。
- 对口型显示“需要正好 1 图 + 1 音频”。
- 时长输入的最大值随工作流变为 10 或 15。
- 不支持的分辨率与比例选项禁用，而不是提交后才报错。
- 现有“生成音频”开关不映射为 AutoDL H3 请求字段；音频由实际连接的音频引用决定。

### 6.3 比例与分辨率映射

AutoDL 使用组合字符串，节点继续保留用户熟悉的“比例 + 分辨率”控件：

- `9:16 + 768p` -> `768p竖`
- `16:9 + 768p` -> `768p横`
- `1:1 + 768p` -> `768p(1:1)`，仅在支持方形的多图工作流中可用。
- `adaptive` 或 `keep_ratio` 在存在图片时读取第一张图片方向：接近方形时选择 1:1，否则选择横或竖。
- 文生视频没有参考图时，`adaptive` 回退为 9:16。
- AutoDL 下不支持 4:3、3:4、21:9、9:21；选择这些值时禁用运行并提示改为 16:9、9:16 或受支持的 1:1。
- 15 秒工作流不提供 1080p；自动切到 15 秒工作流时，如果原值为 1080p，则 UI 自动降为 768p并明确显示“该工作流最高 768p”。

### 6.4 API 设置页

- 增加内置 provider：`id=autodl`、`name=AutoDL`、`protocol=autodl`。
- 后端支持的 provider protocol 集合加入 `autodl`。
- AutoDL provider 的视频工作流列表来自固定注册表，不允许 API 设置页随意改写字段映射。
- 设置页只显示“已连接 / 未配置 / 鉴权失败”和不计费的“检查连接”按钮。
- 设置页不回显 Token，也不把 Token 写入 `data/api_providers.json`；安全配置继续由 `AUTODL_TOKEN` 或 `.env.autodl` 提供。

## 7. 本地素材与公网 URL

AutoDL 工作流接收图片/音频 URL，无法读取 `127.0.0.1`、`/assets/...` 或 `/output/...` 本地地址。

解析顺序：

1. 已是可访问的 `https://` 或 `http://` 地址：直接使用。
2. 配置了 `PUBLIC_MEDIA_BASE_URL` 或 `PUBLIC_BASE_URL`：生成项目自己的公网素材 URL。
3. 节点已保存用户通过“上传云端”获得的临时 URL：使用该 URL。
4. 其他本地素材：预检失败，提示用户点击“上传云端”，不提交付费任务。

现有“上传云端”能力扩展为图片、视频和音频通用媒体上传，但 AutoDL H3 运行时只接受图片和音频。用户点击按钮是明确上传动作；运行按钮不会静默把素材传到 Litterbox、temp.sh 或其他第三方。

上传映射保存在节点内部时只记录本地源 URL、临时公网 URL、服务名和有效期，不记录任何 Token。过期后要求重新上传。

## 8. 后端结构

### 8.1 独立支持模块

新增聚焦的 `autodl_support.py`，避免继续膨胀 `main.py`。模块职责：

- 安全发现 AutoDL 环境配置。
- 非计费 doctor 检查。
- 固定工作流注册表与自动解析器。
- 请求字段验证和精确 body 构造。
- 提交任务、查询状态、提取结果 URL。
- 将上游异常转成不包含 Token 的用户可读错误。

`main.py` 只负责 FastAPI 路由、画布请求模型适配和本地结果保存。

### 8.2 API 路由

新增：

```text
GET  /api/autodl/status
GET  /api/autodl/workflows
POST /api/autodl/tasks
GET  /api/autodl/tasks/{task_id}
```

- `/status` 使用不存在的 task ID 做不计费检查；`InternalError / 工作流不可用` 视为已鉴权业务响应，401/403 视为认证失败。
- `/workflows` 只返回不含密钥的 UI 元数据。
- `POST /tasks` 完成权威路由、素材 URL 预检、请求构造和一次付费提交，然后立即返回 AutoDL task ID。
- `GET /tasks/{task_id}` 查询同一任务；成功时以 task ID 为幂等键下载结果并返回本地 URL。
- task ID 仅接受受限的字母、数字、点、下划线和连字符，防止路径或 URL 注入。

其他 provider 继续走现有 `/api/canvas-video`。`runVideoNode()` 只在实际 provider 为 AutoDL 时使用新异步端点。

### 8.3 结果保存幂等性

本地文件名包含经过校验的 task ID。查询成功时：

1. 若本地结果已存在且能读取，直接返回现有 URL。
2. 若不存在，立即下载短期 URL到临时文件。
3. 完整下载并通过基本媒体校验后原子改名为最终文件。
4. 下载失败时保留任务成功状态和错误证据，不自动重提付费任务。

## 9. 前端任务生命周期

点击“视频生成”后：

1. 获取当前输入快照并运行前端预检。
2. 创建 Output pending 卡片，保存 provider、工作流模式、解析预览和输入摘要。
3. 调用 `POST /api/autodl/tasks`。
4. 获得 task ID 后立即写入 pending 卡片并保存画布。
5. 轮询 `GET /api/autodl/tasks/{task_id}`。
6. `QUEUED` 显示“排队中”，`RUNNING` 显示“生成中”。
7. `SUCCESS` 将本地视频加入 Output，并保存运行元数据。
8. `FAILED` 保留失败卡片、task ID 和错误原因。

画布重新打开时扫描 AutoDL pending 卡片：

- 有 task ID：继续查询原任务。
- 没有 task ID 但提交请求已经中断：标为“提交结果未知”，不自动重提。
- 任务成功但短期资源已过期且本地无文件：标为无法恢复，不自动重新生成。

同一 pending 任务存在时禁用该节点再次提交。用户必须明确结束/清理旧失败记录后才能发起新的付费任务。

## 10. 运行元数据

Output 项目和生成日志至少保存：

```json
{
  "provider_id": "autodl",
  "provider_name": "AutoDL",
  "workflow_mode": "auto",
  "workflow_id": "minimax_h3_lightx2v_v5",
  "workflow_name": "H3 多图参考生视频",
  "workflow_reason": "连接了 2 张图片，时长 8 秒，无音频",
  "task_id": "<autodl task id>",
  "status": "SUCCESS",
  "duration": 8,
  "aspect_ratio": "9:16",
  "resolution": "768p竖",
  "submitted_at": "<timestamp>",
  "completed_at": "<timestamp>"
}
```

不得保存 Authorization、AUTODL_TOKEN、环境文件路径或包含密钥的请求头。

## 11. 错误处理

### 11.1 提交前错误

- Token 缺失：提示安全配置位置，不要求用户在聊天或画布粘贴 Token。
- Token 无效：提示 AutoDL ComfyUI 分组 Token 鉴权失败。
- 缺少提示词：除不支持 prompt 的对口型工作流外阻止提交。
- 图片/音频数量与工作流不符：显示准确数量要求。
- 本地素材不可公网访问：提示先使用“上传云端”。
- 参考视频连接到 AutoDL：提示当前 H3 工作流不支持视频输入，可手动截取首尾帧后再连入。
- 时长、比例或分辨率不支持：阻止提交并给出可选值。

### 11.2 提交后错误

- 网络超时：保留已获得的 task ID并继续允许查询。
- `QUEUED`/`RUNNING`：继续轮询同一任务，不创建重复任务。
- `FAILED`：展示 AutoDL 返回原因，不自动重试。
- 结果缺失：标记“任务成功但未返回视频”，不自动重提。
- 短期 URL 下载失败或过期：保留 task ID和错误证据，不自动再付费。
- 本地保存失败：显示本地文件错误，不把远程 URL 冒充为已持久保存结果。

## 12. 测试设计

### 12.1 Python 单元测试

- 7 个工作流的固定字段和限制与在线 API 面板一致。
- 自动路由覆盖 0/1/2/9/10 张图片、0/1/3/4 段音频、1/10/11/15/16 秒。
- 单图单音频的对口型关键词与普通多模态分支。
- 首尾帧顺序和正好两张图片校验。
- 横、竖、方形、adaptive 和不支持比例映射。
- 10 秒与 15 秒工作流的 1080p 限制。
- 请求 body 不包含未声明字段。
- doctor 对认证成功业务错误、401 和 403 的判定。
- Token 不出现在日志、响应或异常文本。

### 12.2 后端 API 测试

- 模拟 `QUEUED -> RUNNING -> SUCCESS`。
- 模拟 `FAILED`、网络错误、空结果和过期 URL。
- 成功视频只下载一次，重复查询返回同一本地文件。
- task ID 输入校验。
- 本地素材未公网化时不会调用付费提交端点。
- 任何测试默认使用模拟 AutoDL 服务，不创建真实付费任务。

### 12.3 JavaScript 测试

- 新视频节点默认平台、自动模式和初始工作流候选。
- 输入变化后自动说明更新。
- 自动与手动模式切换。
- 工作流相关控件动态启用、禁用和提示。
- pending 卡片保存 task ID并在重新载入后恢复轮询。
- pending 存在时阻止重复提交。
- Output 保存本地视频和完整、脱敏的运行元数据。

### 12.4 手动验收

1. 运行不计费 doctor，确认认证可用。
2. 新建一条 `Group -> 视频生成 -> Output` 画布链路。
3. 依次验证文生视频、多图 10 秒、多图 15 秒、首尾帧、多图音频和对口型的自动解析显示。
4. 使用模拟 API 完成所有结构与恢复测试。
5. 只有在用户从画布明确点击生成时才允许进行一次真实付费冒烟测试。
6. 真实成功后确认视频已下载到本地、可解码、时长和尺寸正确，并位于连接的 Output 节点。

## 13. 验收标准

- 新建视频节点默认显示 `AutoDL` 和“自动选择”。
- 空节点初始候选为 `minimax_h3_lightx2v_v5`。
- 7 个工作流都可手动选择且请求字段准确。
- 自动路由与本设计第 5 节优先级完全一致。
- 节点清楚显示实际工作流和选择原因。
- 不兼容输入在付费提交前被拦截。
- `QUEUED` 和 `RUNNING` 不会触发重复提交。
- 刷新页面可用已保存 task ID继续查询。
- 成功结果立即持久化到本地并进入连接的 Output。
- 失败记录和历史结果保持可见。
- Token 和敏感请求头不会出现在任何前端或持久化数据中。
- 现有其他 provider、旧画布和用户未提交修改不受影响。
