import pytest
from httpx import AsyncClient
from api.main import app

@pytest.mark.asyncio
async def test_register_and_get_user():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        user_data = {
            "telegram_id": "123456789",
            "phone": "+79991234567",
            "first_name": "Тест",
            "last_name": "Тестов",
            "birth_date": "2000-01-01",
        }
        r = await ac.post("/users/", json=user_data)
        assert r.status_code == 200
        u = r.json()
        assert u["telegram_id"] == "123456789"
        r2 = await ac.get(f"/users/123456789")
        assert r2.status_code == 200
