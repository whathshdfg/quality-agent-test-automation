import { useState } from "react";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const defaultRequirement =
  "用户主动取消未接单订单后，订单状态变为 cancelled。如果订单创建后 3 分钟内没有司机接单，系统自动取消订单。如果司机已接单，用户取消订单时必须记录取消原因。订单取消后司机资源应释放。";

function JsonBlock({ data }) {
  if (!data) {
    return <div className="empty-box">暂无数据</div>;
  }

  return (
    <pre className="json-block">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value ?? "-"}</div>
    </div>
  );
}

function App() {
  const [requirement, setRequirement] = useState(defaultRequirement);
  const [report, setReport] = useState("");
  const [metrics, setMetrics] = useState(null);
  const [trace, setTrace] = useState(null);
  const [coverageMatrix, setCoverageMatrix] = useState(null);
  const [modelMode, setModelMode] = useState("api");
  const [activeTab, setActiveTab] = useState("report");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchMetrics() {
    const response = await fetch(`${API_BASE_URL}/agent/v2/metrics`);
    const data = await response.json();

    if (data.status === "success") {
      setMetrics(data.metrics);
    } else {
      setMetrics(data);
    }
  }

  async function fetchTrace() {
    const response = await fetch(`${API_BASE_URL}/agent/v2/trace`);
    const data = await response.json();

    if (data.status === "success") {
      setTrace(data.trace);
    } else {
      setTrace(data);
    }
  }

  async function fetchLatestReport() {
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/agent/v2/report`);
      const data = await response.json();

      if (data.status === "success") {
        setReport(data.report);
        await fetchMetrics();
        await fetchTrace();
      } else {
        setError(data.message || "暂时没有测试报告，请先运行 Agent。");
      }
    } catch (err) {
      setError(`读取报告失败：${err.message}`);
    }
  }

  async function runAgent() {
    setLoading(true);
    setError("");
    setReport("");
    setMetrics(null);
    setTrace(null);
    setCoverageMatrix(null);
    setActiveTab("report");

    try {
      const response = await fetch(`${API_BASE_URL}/agent/v2/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          requirement,
          model_mode: modelMode,
        }),
      });

      if (!response.ok) {
        throw new Error(`请求失败，HTTP 状态码：${response.status}`);
      }

      const data = await response.json();

      if (data.status !== "success") {
        throw new Error(data.message || "Agent 运行失败");
      }

      setReport(data.report);
      setMetrics(data.metrics);
      setTrace(data.trace);
      setCoverageMatrix(data.coverage_matrix);
    } catch (err) {
      setError(`运行 Agent 失败：${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  const traceList = Array.isArray(trace) ? trace : [];

  return (
    <div className="app">
      <header className="hero">
        <div>
          <p className="eyebrow">Quality Engineering AI Agent</p>
          <h1>测试智能化 AI Agent 控制台</h1>
          <p className="subtitle">
            输入业务需求，触发 RAG 检索、测试用例生成、覆盖率分析、真实接口测试、缺陷分析和报告生成。
          </p>
        </div>
      </header>

      <main className="layout">
        <section className="panel input-panel">
          <div className="panel-title">
            <h2>业务需求输入</h2>
            <span>POST /agent/v2/run</span>
          </div>

          <div className="mode-control" aria-label="模型运行模式">
            <button
              className={modelMode === "api" ? "mode-button active" : "mode-button"}
              onClick={() => setModelMode("api")}
              disabled={loading}
            >
              API 模型
            </button>
            <button
              className={modelMode === "rule" ? "mode-button active" : "mode-button"}
              onClick={() => setModelMode("rule")}
              disabled={loading}
            >
              规则模式
            </button>
          </div>

          <textarea
            value={requirement}
            onChange={(event) => setRequirement(event.target.value)}
            placeholder="请输入业务需求..."
          />

          <div className="button-row">
            <button className="primary-button" onClick={runAgent} disabled={loading}>
              {loading ? "Agent 运行中..." : "运行 Agent"}
            </button>

            <button className="secondary-button" onClick={fetchLatestReport} disabled={loading}>
              读取最近报告
            </button>
          </div>

          {error && <div className="error-box">{error}</div>}

          <div className="tips">
            <strong>运行前确认：</strong>
            <p>后端服务需要先启动：uvicorn app.api_server:app --reload</p>
          </div>
        </section>

        <section className="panel result-panel">
          <div className="panel-title">
            <h2>Agent 运行结果</h2>
            <span>{API_BASE_URL}</span>
          </div>

          <div className="metrics-grid">
            <MetricCard label="测试用例数" value={metrics?.test_case_count} />
            <MetricCard label="通过率" value={metrics ? `${metrics.pass_rate}%` : "-"} />
            <MetricCard label="需求覆盖率" value={metrics ? `${metrics.requirement_coverage_rate}%` : "-"} />
            <MetricCard label="参数覆盖率" value={metrics ? `${metrics.parameter_coverage_rate}%` : "-"} />
            <MetricCard label="风险覆盖率" value={metrics ? `${metrics.risk_coverage_rate}%` : "-"} />
            <MetricCard label="失败用例数" value={metrics?.failed_cases} />
            <MetricCard label="自动补充次数" value={metrics?.enhancement_count} />
            <MetricCard label="剩余缺口" value={metrics?.coverage_gap_count} />
          </div>

          <div className="tabs">
            <button
              className={activeTab === "report" ? "tab active" : "tab"}
              onClick={() => setActiveTab("report")}
            >
              测试报告
            </button>
            <button
              className={activeTab === "metrics" ? "tab active" : "tab"}
              onClick={() => setActiveTab("metrics")}
            >
              Metrics 指标
            </button>
            <button
              className={activeTab === "coverage" ? "tab active" : "tab"}
              onClick={() => setActiveTab("coverage")}
            >
              覆盖矩阵
            </button>
            <button
              className={activeTab === "trace" ? "tab active" : "tab"}
              onClick={() => setActiveTab("trace")}
            >
              Trace 链路
            </button>
          </div>

          <div className="output-area">
            {activeTab === "report" && (
              report ? (
                <pre className="report-block">{report}</pre>
              ) : (
                <div className="empty-box">运行 Agent 后，这里会展示测试报告。</div>
              )
            )}

            {activeTab === "metrics" && <JsonBlock data={metrics} />}

            {activeTab === "coverage" && <JsonBlock data={coverageMatrix} />}

            {activeTab === "trace" && (
              traceList.length > 0 ? (
                <div className="trace-list">
                  {traceList.map((item, index) => (
                    <div className="trace-item" key={`${item.node_name}-${index}`}>
                      <div className="trace-header">
                        <span className="trace-index">#{index + 1}</span>
                        <span className="trace-node">{item.node_name}</span>
                        <span className="trace-status">{item.status}</span>
                      </div>
                      <div className="trace-action">{item.action}</div>
                      <div className="trace-time">{item.timestamp}</div>
                      <pre>{JSON.stringify(item.detail, null, 2)}</pre>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-box">运行 Agent 后，这里会展示执行链路。</div>
              )
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
