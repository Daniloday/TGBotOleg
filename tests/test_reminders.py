import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.features.notes.reminders import parse_reminder_text


class RemindersTest(unittest.TestCase):
    def test_schedules_for_today_when_time_is_in_future(self) -> None:
        now = datetime(2026, 5, 10, 10, 0, tzinfo=ZoneInfo("Europe/Kiev"))

        reminder = parse_reminder_text("Call Alex 12:56", now)

        self.assertIsNotNone(reminder)
        assert reminder is not None
        self.assertEqual(reminder.text, "Call Alex")
        self.assertEqual(reminder.remind_at, datetime(2026, 5, 10, 12, 56, tzinfo=ZoneInfo("Europe/Kiev")))

    def test_schedules_for_tomorrow_when_time_has_passed(self) -> None:
        now = datetime(2026, 5, 10, 15, 0, tzinfo=ZoneInfo("Europe/Kiev"))

        reminder = parse_reminder_text("Call Alex 12:56", now)

        self.assertIsNotNone(reminder)
        assert reminder is not None
        self.assertEqual(reminder.remind_at, datetime(2026, 5, 11, 12, 56, tzinfo=ZoneInfo("Europe/Kiev")))

    def test_schedules_for_next_year_when_specific_date_has_passed(self) -> None:
        now = datetime(2026, 5, 10, 15, 0, tzinfo=ZoneInfo("Europe/Kiev"))

        reminder = parse_reminder_text("Call Alex 4.05 12:56", now)

        self.assertIsNotNone(reminder)
        assert reminder is not None
        self.assertEqual(reminder.text, "Call Alex")
        self.assertEqual(reminder.remind_at, datetime(2027, 5, 4, 12, 56, tzinfo=ZoneInfo("Europe/Kiev")))

    def test_without_time_is_not_reminder(self) -> None:
        self.assertIsNone(parse_reminder_text("Plain note", datetime.now().astimezone()))


if __name__ == "__main__":
    unittest.main()
