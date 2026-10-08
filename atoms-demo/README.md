# Quality Agent Studio Atoms-Demo

Quality Agent Studio 是 `quality-agent` 项目的独立可视化演示层，用于展示从业务需求输入，到需求规则拆解、测试点生成、测试用例规划、覆盖缺口分析和定向补充的完整流程。

当前版本采用本地可解释规则引擎和 localStorage，不上传用户需求，不依赖外部模型 API。

## 目标用户

- 测试人员：快速产出结构化测试点和测试用例。
- 产品经理：检查需求中的异常、参数和风险覆盖。
- 开发人员：围绕状态流转、幂等性和数据一致性补充回归场景。

## 核心功能

- 新建测试任务并输入自然语言需求。
- 选择业务类型和风险关注标签。
- 生成结构化需求规则、分层测试点和测试用例。
- 计算需求、功能、参数、风险和综合覆盖率。
- 识别覆盖缺口，并按维度补充用例或一键补齐。
- 编辑、删除、复制、新增测试用例，修改执行状态。
- 使用 localStorage 自动保存任务。
- 导出 Markdown 报告和 JSON 数据。

## 技术栈

React、Vite、TypeScript、React Router、Vitest、Lucide React、原生 CSS、localStorage。

## 目录结构

```text
atoms-demo/
|-- src/
|   |-- data/          # 示例需求
|   |-- features/      # 规则分析、测试点、用例、覆盖率、补充逻辑
|   |-- hooks/         # 任务状态 Hook
|   |-- services/      # localStorage 服务
|   |-- styles/        # 全局样式
|   |-- utils/         # ID 和导出工具
|   |-- App.tsx
|   `-- main.tsx
|-- package.json
|-- vite.config.ts
`-- README.md
```

## 本地安装

```powershell
cd atoms-demo
npm install
```

## 本地启动

```powershell
npm run dev
```

## 测试

```powershell
npm test
```

## 构建

```powershell
npm run build
```

## 数据持久化

任务保存在当前浏览器的 `quality_agent_studio_tasks_v1` localStorage 键中。应用会处理空数据、损坏 JSON 和字段缺失等情况。清除浏览器数据可能导致记录丢失。

## 部署

该应用是静态 Web 应用，使用 HashRouter，适合部署到 Vercel、Netlify 或 GitHub Pages。

最短部署步骤：

```powershell
cd atoms-demo
npm install
npm run build
```

然后将 `dist/` 目录发布到静态托管平台。若使用 Vercel 或 Netlify，唯一需要用户完成的是授权对应平台访问仓库或上传构建产物。

## 推荐演示流程

1. 打开工作台。
2. 进入示例需求，选择支付业务示例。
3. 查看生成的需求规则、测试点和测试用例。
4. 在覆盖分析中查看缺口。
5. 删除一条风险维度用例后，演示一键补齐缺口。
6. 编辑一条用例标题或步骤。
7. 修改执行状态为已通过或已失败。
8. 刷新页面，验证任务仍可打开。
9. 导出 Markdown 报告。

## 当前限制

- 当前版本不连接 FastAPI，不调用 V2/V3 后端。
- 当前版本不调用真实 LLM，结果来自本地规则引擎。
- localStorage 仅适合单浏览器演示，不适合团队协作。
- 测试用例是建议性资产，不能替代真实接口执行结果。

## 后续扩展

- 接入现有 FastAPI。
- 调用 V2 九节点工作流。
- 使用 V3 任务 API 创建异步任务。
- 使用 SSE 展示节点执行状态。
- 接入真实 LLM。
- 使用 SQLite 或 Supabase 做服务端持久化。
- 支持团队协作和权限。
- 执行真实接口测试。
- 展示 Trace 和 Metrics。
