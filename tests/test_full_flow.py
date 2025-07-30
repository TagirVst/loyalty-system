import pytest
from httpx import AsyncClient
from api.main import app

@pytest.mark.asyncio
async def test_full_flow():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Регистрация пользователя
        user = {
            "telegram_id": "22222",
            "phone": "+79991112233",
            "first_name": "Мария",
            "last_name": "Иванова",
            "birth_date": "1999-09-09",
        }
        r = await ac.post("/users/", json=user)
        assert r.status_code == 200
        # Профиль
        p = await ac.get("/users/22222")
        assert p.status_code == 200
        # Генерация кода
        r = await ac.post("/codes/generate", params={"user_id": p.json()["id"]})
        assert r.status_code == 200
        code = r.json()["code"]
        # Использование кода (имитация заказа)
        r = await ac.post("/codes/use", params={"code_value": code})
        assert r.status_code == 200
        # Отзыв
        r = await ac.post("/feedback/review", json={"user_id": p.json()["id"], "score": 9, "text": "Все супер!"})
        assert r.status_code == 200
        # Идея
        r = await ac.post("/feedback/idea", json={"user_id": p.json()["id"], "text": "Добавьте чизкейки!"})
        assert r.status_code == 200
