import unittest

from app.features.notes.router import close_keyboard, delete_push_keyboard


class RouterKeyboardTest(unittest.TestCase):
    def test_delete_push_keyboard_has_icons_and_callbacks(self) -> None:
        keyboard = delete_push_keyboard("p123")

        buttons = keyboard.inline_keyboard[0]
        self.assertEqual([button.text for button in buttons], ["📥 В инбокс", "🗑 Удалить"])
        self.assertEqual(
            [button.callback_data for button in buttons],
            ["push:inbox:p123", "push:delete:p123"],
        )

    def test_close_keyboard_has_icon_and_callback(self) -> None:
        keyboard = close_keyboard()

        button = keyboard.inline_keyboard[0][0]
        self.assertEqual(button.text, "✖ Закрыть")
        self.assertEqual(button.callback_data, "push:close")


if __name__ == "__main__":
    unittest.main()
