from uuid import uuid4

from httpx import AsyncClient


async def test_create_and_list_messages_chronologically(client: AsyncClient) -> None:
    session_response = await client.post("/api/sessions", json={"title": "Sales Analysis"})
    session_id = session_response.json()["id"]

    first = await client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "user", "content": "Build a sales dashboard"},
    )
    second = await client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "assistant", "content": "Stored for later processing"},
    )
    response = await client.get(f"/api/sessions/{session_id}/messages")

    assert first.status_code == 201
    assert second.status_code == 201
    assert response.status_code == 200
    assert [message["role"] for message in response.json()] == ["user", "assistant"]
    assert [message["content"] for message in response.json()] == [
        "Build a sales dashboard",
        "Stored for later processing",
    ]


async def test_message_for_unknown_session_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/sessions/{uuid4()}/messages",
        json={"role": "user", "content": "This session does not exist"},
    )

    assert response.status_code == 404


async def test_blank_message_is_rejected(client: AsyncClient) -> None:
    session_response = await client.post("/api/sessions", json={"title": "Sales Analysis"})
    session_id = session_response.json()["id"]

    response = await client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "user", "content": "   "},
    )

    assert response.status_code == 422
