from loyalty_v2.bots.staff_bot import StaffBot


def test_staff_main_keyboard_is_intentionally_small() -> None:
    markup = StaffBot.main_keyboard()
    labels = [button.text for row in markup.keyboard for button in row]
    assert labels == ["Новая продажа", "Выйти"]


def test_sale_is_primary_staff_action() -> None:
    assert StaffBot.main_keyboard().keyboard[0][0].text == "Новая продажа"


def test_reward_callback_stays_within_telegram_limit() -> None:
    callback = "rw:" + "00000000-0000-0000-0000-000000000000"
    assert len(callback.encode()) <= 64
