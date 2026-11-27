import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

STORE_URL = "https://store.example.com"
CONSUMER_KEY = "ck_review_secret"
CONSUMER_SECRET = "cs_review_secret"


@pytest.fixture(autouse=True)
def configure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOOCOMMERCE_STORE_URL", STORE_URL)
    monkeypatch.setenv("WOOCOMMERCE_CONSUMER_KEY", CONSUMER_KEY)
    monkeypatch.setenv("WOOCOMMERCE_CONSUMER_SECRET", CONSUMER_SECRET)


def mock_httpx(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr("app.services.woocommerce.httpx.Client", client_factory)


def sample_review(review_id: int = 10, **overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": review_id,
        "date_created": "2026-11-27T10:00:00",
        "date_created_gmt": "2026-11-27T04:30:00",
        "product_id": 22,
        "status": "approved",
        "reviewer": "John Doe",
        "reviewer_email": "john.doe@example.com",
        "review": "Nice album!",
        "rating": 5,
        "verified": False,
        "reviewer_avatar_urls": {
            "24": "https://example.com/24.png",
            "48": "https://example.com/48.png",
            "96": "https://example.com/96.png",
        },
        "_links": {"self": [{"href": f"https://store.example.com/wp-json/wc/v3/products/reviews/{review_id}"}]},
    }
    item.update(overrides)
    return item


def test_create_review_required_and_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(201, json=sample_review(10)))

    with TestClient(app) as client:
        req_only = client.post("/products/reviews", json={"product_id": 22, "review": "Nice album!"})
        full = client.post(
            "/products/reviews",
            json={
                "product_id": 22,
                "review": "Nice album!",
                "reviewer": "John Doe",
                "reviewer_email": "john.doe@example.com",
                "rating": 5,
                "status": "approved",
            },
        )
        rating_zero = client.post("/products/reviews", json={"product_id": 22, "review": "Ok", "rating": 0})
        rating_low = client.post("/products/reviews", json={"product_id": 22, "review": "Ok", "rating": -1})
        rating_high = client.post("/products/reviews", json={"product_id": 22, "review": "Ok", "rating": 6})
        bad_email = client.post(
            "/products/reviews",
            json={"product_id": 22, "review": "Ok", "reviewer_email": "not-an-email"},
        )
        missing_pid = client.post("/products/reviews", json={"review": "Ok"})
        missing_review = client.post("/products/reviews", json={"product_id": 22})

    assert req_only.status_code == 201
    assert full.status_code == 201
    assert rating_zero.status_code == 201
    assert rating_low.status_code == 422
    assert rating_high.status_code == 422
    assert bad_email.status_code == 422
    assert missing_pid.status_code == 422
    assert missing_review.status_code == 422


def test_get_and_list_reviews_with_all_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wp-json/wc/v3/products/reviews/10":
            return httpx.Response(200, json=sample_review(10))
        if request.url.path == "/wp-json/wc/v3/products/reviews":
            assert request.url.params["context"] == "edit"
            assert request.url.params["page"] == "2"
            assert request.url.params["per_page"] == "5"
            assert request.url.params["search"] == "album"
            assert request.url.params["dates_are_gmt"] == "true"
            assert request.url.params["include"] == "10,11"
            assert request.url.params["exclude"] == "1"
            assert request.url.params["offset"] == "1"
            assert request.url.params["order"] == "asc"
            assert request.url.params["orderby"] == "id"
            assert request.url.params["reviewer"] == "2,3"
            assert request.url.params["reviewer_exclude"] == "4"
            assert request.url.params["reviewer_email"] == "john.doe@example.com"
            assert request.url.params["product"] == "22,23"
            assert request.url.params["status"] == "all"
            return httpx.Response(200, json=[sample_review(10)])
        raise AssertionError(f"Unexpected path: {request.url.path}")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        single = client.get("/products/reviews/10")
        bad_id = client.get("/products/reviews/0")
        listed = client.get(
            "/products/reviews",
            params={
                "context": "edit",
                "page": 2,
                "per_page": 5,
                "search": "album",
                "after": "2026-11-01T00:00:00",
                "before": "2026-11-30T23:59:59",
                "dates_are_gmt": True,
                "include": [10, 11],
                "exclude": [1],
                "offset": 1,
                "order": "asc",
                "orderby": "id",
                "reviewer": [2, 3],
                "reviewer_exclude": [4],
                "reviewer_email": ["john.doe@example.com"],
                "product": [22, 23],
                "status": "all",
            },
        )

    assert single.status_code == 200
    assert single.json()["id"] == 10
    assert bad_id.status_code == 422
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_update_and_delete_review(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            assert json.loads(request.content) == {"rating": 4, "status": "hold"}
            return httpx.Response(200, json=sample_review(10, rating=4, status="hold"))
        if request.method == "DELETE":
            assert request.url.params["force"] == "true"
            return httpx.Response(200, json={"deleted": True, "previous": sample_review(10)})
        raise AssertionError("Unexpected method")

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        upd = client.put("/products/reviews/10", json={"rating": 4, "status": "hold"})
        empty_upd = client.put("/products/reviews/10", json={})
        bad_status = client.put("/products/reviews/10", json={"status": "all"})
        no_force = client.delete("/products/reviews/10")
        false_force = client.delete("/products/reviews/10", params={"force": False})
        with_force = client.delete("/products/reviews/10", params={"force": True})

    assert upd.status_code == 200
    assert upd.json()["rating"] == 4
    assert empty_upd.status_code == 422
    assert bad_status.status_code == 422
    assert no_force.status_code == 400
    assert false_force.status_code == 400
    assert with_force.status_code == 200
    assert with_force.json()["deleted"] is True
    assert with_force.json()["previous"]["id"] == 10


def test_batch_reviews_total_limit_and_partial_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/wp-json/wc/v3/products/reviews/batch"
        return httpx.Response(
            200,
            json={
                "create": [
                    sample_review(15),
                    {"id": 0, "error": {"code": "woocommerce_rest_comment_duplicate", "message": "Duplicate"}},
                ],
                "update": [sample_review(10, reviewer="Jane Doe")],
                "delete": [{"deleted": True, "previous": sample_review(12)}],
            },
        )

    mock_httpx(monkeypatch, handler)

    with TestClient(app) as client:
        ok = client.post(
            "/products/reviews/batch",
            json={
                "create": [
                    {"product_id": 22, "review": "Great!"},
                    {"product_id": 22, "review": "Duplicate"},
                ],
                "update": [{"id": 10, "reviewer": "Jane Doe"}],
                "delete": [12],
            },
        )
        over_100 = client.post(
            "/products/reviews/batch",
            json={
                "create": [{"product_id": 22, "review": f"R{i}"} for i in range(60)],
                "delete": list(range(1, 42)),
            },
        )

    assert ok.status_code == 200
    assert ok.json()["create"][1]["error"]["code"] == "woocommerce_rest_comment_duplicate"
    assert ok.json()["delete"][0]["deleted"] is True
    assert over_100.status_code == 422


def test_review_errors_and_swagger(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_httpx(monkeypatch, lambda request: httpx.Response(403, json={"message": CONSUMER_SECRET}))
    with TestClient(app) as client:
        perm = client.get("/products/reviews")
        schema = client.get("/openapi.json").json()

    assert perm.status_code == 403
    assert CONSUMER_SECRET not in perm.text
    assert schema["paths"]["/products/reviews"]["get"]["tags"] == ["Product Reviews"]
    assert schema["paths"]["/products/reviews/batch"]["post"]["tags"] == ["Product Reviews"]
