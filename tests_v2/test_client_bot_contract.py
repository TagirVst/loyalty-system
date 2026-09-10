from loyalty_v2.bots.client_bot import ClientBot


def test_main_keyboard_contains_primary_customer_actions() -> None:
    markup = ClientBot.main_keyboard()
    labels = [button.text for row in markup.keyboard for button in row]
    assert labels == ["Получить код", "Мои награды", "История", "Профиль"]


def test_identification_is_primary_action() -> None:
    markup = ClientBot.main_keyboard()
    assert markup.keyboard[0][0].text == "Получить код"
