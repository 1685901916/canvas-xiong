# Infinite Canvas 本地 RealESRGAN 画质提升节点设计

日期：2026-07-17  
状态：用户已批准交互方向，等待书面规格确认后进入实施计划  
约束：仅本地修改，不 commit、不 push、不向官方仓库提交

## 1. 目标

在经典无限画布中增加一个独立的本地图片处理节点，让用户从图片节点右侧端口拉线后，点击“画质提升”即可创建并连接 RealESRGAN 节点。

目标工作流：

```text
Image -> RealESRGAN 画质提升 -> Output
```

原始图片必须保留。增强结果写入或追加到右侧 Output 节点，不能覆盖原 Image 节点。

## 2. 已确认的本机条件

- 模型文件：`C:\Users\Arthur\.cache\realesrgan\RealESRGAN_x4plus_anime_6B.pth`
- 推理 Python：`C:\Users\Arthur\AppData\Local\Programs\Python\Python312\python.exe`
- `realesrgan==0.3.0`
- `basicsr==1.4.2`
- `torch==2.11.0+cu126`
- `torchvision==0.26.0+cu126`
- CUDA 可用，设备为 `NVIDIA GeForce RTX 4060 Laptop GPU`
- 当前 `realesrgan` 直接导入会因 `torchvision.transforms.functional_tensor` 已移除而失败。
- 在独立工作进程中注册最小兼容模块后，`realesrgan` 和 `RRDBNet` 可以成功导入；实施时不修改全局 site-packages。

现有 `workflows/upscale.json` 使用 SeedVR2/ComfyUI，不是本次要求的本地 RealESRGAN 线路，因此继续保留，互不替换。

## 3. 用户交互

### 3.1 创建入口

在图片、分组或 Output 的右侧端口拉线菜单中新增：

```text
画质提升
```

图标建议使用 `sparkles` 或 `scan-line`。

菜单点击后：

1. 在鼠标释放位置创建 `realesrgan` 节点。
2. 自动建立来源节点到 RealESRGAN 节点的连接。
3. 不立即运行推理。

空白画布的节点创建菜单也增加同一入口，便于先建节点再连接图片。

节点标题显示：

```text
RealESRGAN 画质提升
```

### 3.2 节点控件

节点提供以下可见控件：

- 输入图片预览，只使用第一张有效图片。
- 本地模型下拉框。
  - 初始选项：`RealESRGAN_x4plus_anime_6B`
  - 选项来自后端安全发现接口，不在前端长期硬编码绝对路径。
- 放大倍率下拉框：
  - `2×`
  - `4×`，默认值
- 运行设备只读状态：
  - 正常时显示 `CUDA · RTX 4060`
  - CUDA 不可用时允许显示 `CPU`，但需要明确提示速度较慢
- “开始提升”按钮。
- 运行中、完成、失败状态，沿用现有生成节点的状态样式。

不在第一版暴露 tile、tile padding、半精度等底层参数；这些由后端自动管理。

### 3.3 输出行为

点击“开始提升”后：

1. 读取已连接来源中的第一张有效图片。
2. 调用本地 RealESRGAN 后端。
3. 成功后创建或复用该节点右侧已连接的 Output。
4. 将增强图片追加到 Output。
5. 保留原图、已有 Output 图片和其他节点。
6. 记录模型、倍率、输入尺寸、输出尺寸、设备与耗时。

如果 RealESRGAN 节点已经连接 Output，则复用该 Output，不重复创建。

节点应支持现有的级联运行：

```text
Image -> RealESRGAN -> Output -> 下游图片生成/编辑节点
```

## 4. 画布数据结构

新增节点类型：

```json
{
  "id": "realesr_xxx",
  "type": "realesrgan",
  "x": 100,
  "y": 100,
  "w": 360,
  "h": 390,
  "model": "RealESRGAN_x4plus_anime_6B",
  "scale": 4,
  "device": "auto",
  "inputs": [],
  "runStatus": "",
  "runError": ""
}
```

兼容要求：

- 旧画布完全不需要迁移。
- 新字段缺失时使用上述默认值。
- `realesrgan` 加入图片型生成/处理节点集合、连接校验、输入同步、级联执行和日志展示。
- RealESRGAN 输出可以连接 Output，也可以作为图片来源继续连接其他图片处理/生成节点。

## 5. 后端接口

### 5.1 状态与模型发现

新增只读接口：

```text
GET /api/realesrgan/status
```

返回示例：

```json
{
  "ok": true,
  "python": "C:\\Users\\Arthur\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
  "cuda": true,
  "device": "NVIDIA GeForce RTX 4060 Laptop GPU",
  "models": [
    {
      "id": "RealESRGAN_x4plus_anime_6B",
      "name": "RealESRGAN x4plus Anime 6B",
      "native_scale": 4
    }
  ]
}
```

接口不得返回 OAuth、Cookie、API Key 或其他凭据。

### 5.2 提升接口

新增：

```text
POST /api/realesrgan/upscale
```

请求：

```json
{
  "source_url": "/assets/output/online_xxx.png",
  "model": "RealESRGAN_x4plus_anime_6B",
  "scale": 4
}
```

成功响应：

```json
{
  "ok": true,
  "url": "/assets/output/realesrgan_xxx.png",
  "model": "RealESRGAN_x4plus_anime_6B",
  "scale": 4,
  "source_width": 768,
  "source_height": 1024,
  "width": 3072,
  "height": 4096,
  "device": "cuda",
  "run_ms": 1234
}
```

## 6. 本地推理工作进程

新增独立 worker 脚本，由当前 FastAPI 服务通过异步子进程调用系统 Python，而不是把大型 Torch 依赖安装进项目自带 Python。

worker 职责：

1. 注册 `torchvision.transforms.functional_tensor` 最小兼容模块。
2. 构建动漫 6B 对应的 `RRDBNet`。
3. 加载白名单中的本地 `.pth` 模型。
4. 使用 CUDA 和半精度执行；CUDA 不可用时回退 CPU。
5. 原生模型执行 4× 推理。
6. `scale=2` 时使用 RealESRGAN 的输出倍率能力生成最终 2× 尺寸。
7. 输出 PNG 到应用现有 `assets/output` 目录。
8. 仅在 stdout 输出结构化 JSON；错误写入 stderr，并由后端脱敏后返回。

后端使用单任务 GPU 信号量，避免同一张 RTX 4060 同时加载多个 RealESRGAN 任务导致显存不足。

显存处理策略：

- 默认自动 tile。
- 首次使用合适的 tile 尺寸。
- 捕获 CUDA OOM 后清理缓存，并使用更小 tile 自动重试一次。
- 第二次仍失败则返回明确错误，不无限重试。

## 7. 路径与安全边界

- 前端只能提交模型 ID，不能提交任意模型绝对路径。
- 后端把模型 ID映射到固定模型目录中的白名单文件。
- `source_url` 只能解析到应用允许的本地图片目录，例如上传目录、素材目录和 `assets/output`。
- 禁止 `..` 路径穿越。
- 禁止把用户输入拼接为 shell 命令；子进程参数必须使用参数数组。
- 只接受可由 Pillow/OpenCV 解码的图片。
- 对输入像素数、文件大小、执行超时和输出像素数设置上限。
- 不调用任何第三方 API，不消耗图片生成 API 额度。

## 8. 错误处理

前端需要显示可理解的错误：

- 未连接图片：`请先连接一张图片`
- 本地模型不存在：`未找到 RealESRGAN 本地模型`
- Python 环境不可用：`RealESRGAN 运行环境不可用`
- 图片格式不支持：`输入不是可处理的图片`
- 显存不足：`显存不足，请选择 2× 或使用更小的原图`
- 运行超时：`画质提升超时`
- worker 没有返回文件：`RealESRGAN 未生成输出图片`

失败时不得删除输入图片，也不得向 Output 写入空白条目。

## 9. 日志与结果元数据

沿用画布现有生成日志，至少记录：

```json
{
  "platform": "Local RealESRGAN",
  "model": "RealESRGAN_x4plus_anime_6B",
  "scale": 4,
  "source_width": 768,
  "source_height": 1024,
  "width": 3072,
  "height": 4096,
  "device": "cuda",
  "run_ms": 1234,
  "status": "success"
}
```

日志不得记录本机令牌或敏感环境变量。

## 10. 测试策略

实施必须按测试先行：

1. 后端模型发现测试先失败，再实现状态接口。
2. 路径白名单与路径穿越拒绝测试先失败，再实现解析。
3. worker 参数、2×/4×、输出元数据和错误映射测试先失败，再实现调用层。
4. 前端节点默认值、菜单选项、连接规则、输入同步和级联分发测试先失败，再修改 `canvas.js`。
5. 运行 Python 编译和 JavaScript 语法检查。
6. 使用一张小型本地图片做一次真实 CUDA 推理，核对：
   - 输出文件存在；
   - 2×/4×尺寸正确；
   - 原图未修改；
   - Output 收到结果；
   - 无第三方网络请求。
7. 使用浏览器验证用户截图中的拉线菜单出现“画质提升”，创建节点后可选择倍率，并能自动连接 Output。

真实推理验证只执行满足验收所需的最少次数。

## 11. 验收标准

- 图片端口拉线菜单能看到并点击“画质提升”。
- 点击后创建 `RealESRGAN 画质提升` 节点并自动连接来源图片。
- 节点能发现并选择本地 `RealESRGAN_x4plus_anime_6B`。
- 节点可选择 `2×` 或 `4×`，默认 `4×`。
- 点击运行后使用本机 CUDA 推理。
- 原始 Image 节点不被覆盖。
- 结果自动写入或追加到一个已连接的 Output。
- 级联运行和继续连接下游图片节点可用。
- 模型缺失、输入缺失、格式错误、OOM 和超时都有明确提示。
- 旧画布、现有 API生成、ModelScope、ComfyUI、RunningHub、视频、LLM 等功能不受影响。
- 不修改系统 site-packages，不读取凭据，不调用第三方图片 API。
- 不 commit、不 push、不向官方仓库提交。

## 12. 非目标

第一版不包含：

- 人脸修复/GFPGAN。
- 多张图片批处理队列。
- 任意倍率文本输入。
- 暴露 tile、半精度、线程数等高级参数。
- 自动下载其他模型。
- 替换现有 ComfyUI/SeedVR2 超分功能。
- 修改或覆盖原始图片。
