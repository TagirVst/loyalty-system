from pathlib import Path


def test_notification_outbox_supports_retry_and_idempotency():
    text = Path("src/loyalty_v2/db/notification_models.py").read_text()
    assert "class NotificationOutbox" in text
    assert "idempotency_key" in text
    assert "next_attempt_at" in text
    assert "max_attempts" in text


def test_notification_preferences_separate_marketing():
    text = Path("src/loyalty_v2/db/notification_models.py").read_text()
    assert "marketing_enabled" in text
    assert "service_enabled" in text


def test_delivery_provider_is_abstracted_from_telegram():
    service = Path("src/loyalty_v2/application/notification_service.py").read_text()
    adapter = Path("src/loyalty_v2/application/telegram_notification_provider.py").read_text()
    assert "class NotificationProvider(Protocol)" in service
    assert "Bot" not in service
    assert "class TelegramNotificationProvider" in adapter
    assert "send_message" in adapter
