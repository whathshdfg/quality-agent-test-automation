# Quality Agent Studio Atoms-Demo

Quality Agent Studio 是一个需求驱动的应用生成与质量评审工作台。用户用自然语言描述应用，服务端调用真实 OpenAI 兼容模型生成完整 `index.html`，经过结构与安全校验后，在隔离 iframe 中运行。用户可以继续提出修改、切换或恢复历史版本，并下载生成源码。

原有“需求规则拆解 → 测试点 → 测试用例 → 覆盖缺口补充”能力保留在“质量工作台”，作为生成应用后的延展能力。

## 已实现能力

- 需求对话、真实模型代码生成和 SSE 阶段事件。
- 单文件 HTML/CSS/JavaScript 应用生成，无构建步骤和外部依赖。
- 生成结果结构校验、安全检查和最多两次自动修复。
- `sandbox="allow-scripts"` iframe 运行预览，不授予同源权限。
- CSP 禁用生成应用的网络、外部脚本、表单提交、嵌套页面和插件内容。
- 受控 `postMessage` 存储桥，支持生成应用在浏览器中保存数据。
- SQLite 保存项目、对话和所有代码版本。
- 历史版本查看、恢复为新版本，以及 HTML 源码下载。
- 模型未配置、调用失败、校验失败和连接失败的可见错误及重试入口。
- 测试资产生成、编辑、覆盖缺口分析和 Markdown/JSON 导出。

## 目录结构

```text
atoms-demo/
|-- backend/               # 独立 FastAPI、SQLite、模型生成与校验
|-- src/studio/            # 应用生成工作区、API、隔离预览
|-- src/features/          # 原有测试资产规则引擎
|-- Dockerfile             # 前后端单服务生产镜像
|-- render.yaml            # Render Blueprint
|-- package.json
`-- vite.config.ts
```

本目录完全独立，没有修改现有 V1、V2、V3 工作流模块。

## 本地配置

服务端沿用仓库根目录的 OpenAI 兼容环境变量，也可在启动终端中设置：

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

API Key 只由服务端读取，不能放入 `VITE_` 前缀变量或前端代码。

## 本地启动

首次安装：

```powershell
cd atoms-demo
npm install
```

终端一，启动独立 API：

```powershell
cd atoms-demo
npm run dev:api
```

终端二，启动前端：

```powershell
cd atoms-demo
npm run dev -- --host 127.0.0.1
```

打开 `http://127.0.0.1:5173/`。Vite 会将 `/api` 代理到 `http://127.0.0.1:8001`。

也可以构建前端后仅运行 FastAPI，由同一端口提供页面和 API：

```powershell
cd atoms-demo
npm run build
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

然后打开 `http://127.0.0.1:8001/`。

## 测试

```powershell
cd atoms-demo
npm test
npm run test:backend
npm run build
```

原项目回归测试需要在仓库根目录执行：

```powershell
python -m pytest
```

## 生成流程

```text
创建项目
  → 分析需求与当前版本
  → 调用真实模型生成结构化文件
  → 校验 JSON、HTML 结构、体积和危险能力
  → 校验失败时携带错误自动修复（最多两次）
  → SQLite 保存新版本
  → 沙箱预览
```

系统展示的是实际执行阶段和校验错误，不展示或伪造模型内部思考过程。

## 安全边界

当前只接受一个不超过 300 KB 的 `index.html`。生成代码禁止外部脚本、远程资源、网络请求、嵌套页面、Cookie、宿主窗口访问及直接使用 Web Storage。预览 iframe 只有 `allow-scripts` 权限，未设置 `allow-same-origin`。

这些边界适合产品 Demo，不能替代面向不可信代码的容器级隔离。若扩展到 npm 依赖、多文件构建或服务端代码，应使用独立容器、资源限制、网络策略和任务超时。

## 数据持久化

- 项目、对话和源码版本保存在 `STUDIO_DB_PATH` 指向的 SQLite 数据库，默认位置为 `atoms-demo/data/studio.db`。
- 生成应用自身的数据通过存储桥保存在访问者浏览器中，每个项目相互隔离。
- 原质量工作台任务仍使用浏览器 localStorage。

## Render 部署

`render.yaml` 和 `Dockerfile` 已准备好将 React 与 FastAPI 部署为同一个 Web Service。创建 Render Blueprint 时指定：

- 仓库：`https://github.com/whathshdfg/quality-agent-test-automation`
- 分支：`feature/v3`（合并后可改为 `main`）
- Blueprint 路径：`atoms-demo/render.yaml`
- 密钥：在 Render 中填写 `OPENAI_API_KEY`

Blueprint 使用 Starter Web Service 和 1 GB 持久磁盘，将 SQLite 写入 `/data/studio.db`。Render 免费 Web Service 不支持持久磁盘，使用免费实例会在重启或休眠后丢失 SQLite 数据，因此不适合本 Demo 的持久化要求。

部署完成后，访问 `/api/health`，确认 `status` 为 `ok`、`model_configured` 为 `true`，再从未登录浏览器完成一次生成和刷新恢复测试。

## 当前限制

- 每次生成会等待模型返回完整 HTML，复杂应用可能需要一到三分钟。
- 当前仅生成单文件前端应用，不运行 npm 安装、服务端代码或任意 Shell 命令。
- 项目数据没有用户账号隔离；公开链接上的项目历史对所有访问者可见。
- SQLite 单实例适合演示，不适合横向扩容和高并发协作。
- 生成内容仍需要人工评审，安全规则不能证明代码绝对安全。
