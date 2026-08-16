from uuid import uuid4

from httpx import AsyncClient


async def create_session(client: AsyncClient, title: str = "Sales Analysis") -> dict:
    response = await client.post("/api/sessions", json={"title": title})
    assert response.status_code == 201
    return response.json()


async def test_create_and_retrieve_session(client: AsyncClient) -> None:
    created = await create_session(client)

    response = await client.get(f"/api/sessions/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Sales Analysis"
    assert body["messages"] == []
    assert body["database_connection"] is None
    assert body["dashboard"] is None


async def test_list_sessions_orders_by_recent_activity(client: AsyncClient) -> None:
    older = await create_session(client, "Older session")
    await create_session(client, "Newer session")
    message_response = await client.post(
        f"/api/sessions/{older['id']}/messages",
        json={"role": "user", "content": "Touch this session"},
    )
    assert message_response.status_code == 201

    response = await client.get("/api/sessions")

    assert response.status_code == 200
    assert [session["title"] for session in response.json()] == [
        "Older session",
        "Newer session",
    ]


async def test_delete_session(client: AsyncClient) -> None:
    created = await create_session(client)

    delete_response = await client.delete(f"/api/sessions/{created['id']}")
    get_response = await client.get(f"/api/sessions/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


async def test_rename_session(client: AsyncClient) -> None:
    created = await create_session(client)

    response = await client.patch(
        f"/api/sessions/{created['id']}", json={"title": "Executive sales"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Executive sales"


async def test_get_unknown_session(client: AsyncClient) -> None:
    response = await client.get(f"/api/sessions/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
