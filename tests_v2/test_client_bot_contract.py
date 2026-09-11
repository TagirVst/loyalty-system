from pathlib import Path

from loyalty_v2.bots.client_bot import ClientBot


def test_main_keyboard_contains_primary_customer_actions() -> None:
    markup = ClientBot.main_keyboard()
    labels = [button.text for row in markup.keyboard for button in row]
    assert labels == ["Получить код", "Мои награды", "История", "Профиль", "Оставить отзыв", "Уведомления"]


def test_identification_is_primary_action() -> None:
    markup = ClientBot.main_keyboard()
    assert markup.keyboard[0][0].text == "Получить код"


def test_bot_uses_customer_session_and_portal_facade() -> None:
    text = Path("src/loyalty_v2/bots/client_bot.py").read_text()
    assert "CustomerAuthService" in text
    assert "CustomerPortalService" in text
    assert "portal.identification_code" in text
    assert "portal.rewards" in text
    assert "portal.history" in text
    assert "portal.submit_feedback" in text
    assert "portal.notification_preferences" in text
    assert "portal.set_marketing_notifications" in text
    assert "customers.by_identity" not in text
    assert "IdentificationService" not in text


def test_feedback_is_fsm_driven_and_rating_is_bounded() -> None:
    text = Path("src/loyalty_v2/bots/client_bot.py").read_text()
    assert "class FeedbackFlow" in text
    assert "rating not in range(1,6)" in text
    assert "Пропустить" in text
