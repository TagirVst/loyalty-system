from pathlib import Path


def test_notification_outbox_supports_retry_and_idempotency():
    text = Path("src/loyalty_v2/db/notification_models.py").read_text()
    assert "class NotificationOutbox" in text
    assert "idempotency_key" in text
    assert "next_attempt_at" in text
    assert "max_attempts" in text
    assert "recipient_type" in text
    assert "staff_chat" in text


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


def test_reward_issuance_enqueues_service_notification():
    text = Path("src/loyalty_v2/application/reward_service.py").read_text()
    assert 'template_code="reward_issued"' in text
    assert 'idempotency_key=f"reward-issued:{reward.id}"' in text


def test_negative_feedback_routes_to_admin_chat_outbox():
    text = Path("src/loyalty_v2/application/feedback_service.py").read_text()
    assert "enqueue_staff_chat" in text
    assert 'Staff.role == "admin"' in text
    assert 'template_code="negative_feedback"' in text


def test_segment_broadcast_respects_marketing_preferences():
    service = Path("src/loyalty_v2/application/notification_service.py").read_text()
    route = Path("src/loyalty_v2/api/admin_notification_routes.py").read_text()
    assert "enqueue_segment" in service
    assert 'kind="marketing"' in service
    assert "marketing_enabled" in service
    assert '@router.post("/segment"' in route


def test_customer_can_control_marketing_notifications():
    text = Path("src/loyalty_v2/api/customer_routes.py").read_text()
    assert '@router.get("/notification-preferences")' in text
    assert '@router.put("/notification-preferences")' in text
