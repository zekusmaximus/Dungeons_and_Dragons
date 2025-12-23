from pathlib import Path

import pytest


@pytest.fixture()
def spa_index_html():
    repo_root = Path(__file__).resolve().parents[1]
    dist_path = repo_root / "ui" / "dist"
    index_path = dist_path / "index.html"

    dist_existed = dist_path.exists()
    index_existed = index_path.exists()
    original_contents = index_path.read_text(encoding="utf-8") if index_existed else None

    if not dist_existed:
        dist_path.mkdir(parents=True, exist_ok=True)

    index_html = "<!doctype html><html><head><title>SPA</title></head><body>spa</body></html>"
    index_path.write_text(index_html, encoding="utf-8")

    try:
        yield index_html
    finally:
        if index_existed and original_contents is not None:
            index_path.write_text(original_contents, encoding="utf-8")
        else:
            if index_path.exists():
                index_path.unlink()
        if not dist_existed:
            try:
                dist_path.rmdir()
            except OSError:
                pass


def test_api_unknown_returns_json_404(client, spa_index_html):
    response = client.get("/api/unknown")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"] == "Not Found"
    assert spa_index_html not in response.text


def test_spa_fallback_serves_index(client, spa_index_html):
    response = client.get("/unknown-client-route")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == spa_index_html
