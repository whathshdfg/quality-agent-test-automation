import json

from backend.generator import GeneratedApp, parse_generated_app, validate_generated_app
from backend.repository import StudioRepository


VALID_HTML = """<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>订单工作台</title><style>body{font-family:system-ui;margin:0;padding:32px;background:#f5f7fa;color:#172033}main{max-width:800px;margin:auto}button{padding:10px 16px;border:0;background:#176b5b;color:white;cursor:pointer}</style></head><body><main><h1>订单工作台</h1><p>在这里创建和管理业务订单。</p><button id='add'>新增订单</button><section id='orders'></section></main><script>document.querySelector('#add').onclick=()=>{document.querySelector('#orders').textContent='已创建一条新订单';document.body.dataset.clicked='1';};</script></body></html>"""


def test_repository_saves_and_restores_versions(tmp_path):
    repository = StudioRepository(tmp_path / "studio.db")
    project = repository.create_project("订单应用", "生成一个可以新增和筛选订单的业务应用，并保存用户输入的数据。")

    saved = repository.save_version(project["id"], "初始版本", VALID_HTML)
    assert saved["current_version"] == 1
    assert saved["version"]["html"] == VALID_HTML

    restored = repository.restore_version(project["id"], 1)
    assert restored["current_version"] == 2
    assert restored["version"]["html"] == VALID_HTML
    assert len(restored["versions"]) == 2


def test_generated_app_parser_accepts_expected_contract():
    raw = json.dumps(
        {
            "summary": "生成订单列表",
            "files": [{"path": "index.html", "content": VALID_HTML}],
        },
        ensure_ascii=False,
    )
    app = parse_generated_app(raw)
    assert app.summary == "生成订单列表"
    assert validate_generated_app(app) == []


def test_generated_app_validator_rejects_network_and_host_access():
    unsafe = GeneratedApp(
        summary="unsafe",
        html="<html><body><script>fetch('https://example.com'); window.parent.postMessage('x','*')</script></body></html>" * 5,
    )
    errors = validate_generated_app(unsafe)
    assert "不允许发起网络请求" in errors
    assert "不允许访问宿主窗口" in errors
