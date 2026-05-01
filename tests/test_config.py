import unittest
from pathlib import Path

from backend.trading_monitor.config import AppConfig, ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_loads_safe_defaults(self):
        config = load_config({})

        self.assertEqual(config.symbols, ("VOO", "IAU"))
        self.assertEqual(config.gui.host, "127.0.0.1")
        self.assertFalse(config.auto_trade_enabled)
        self.assertEqual(config.alerts.min_confidence, 75)
        self.assertEqual(config.db_path, Path("data/trading_monitor.sqlite"))

    def test_watchlist_is_normalized_and_deduplicated(self):
        config = load_config({"WATCHLIST": "voo, iau, VOO, qqq"})

        self.assertEqual(config.symbols, ("VOO", "IAU", "QQQ"))

    def test_invalid_symbol_is_rejected(self):
        with self.assertRaises(ValueError):
            load_config({"WATCHLIST": "VOO,not valid"})

    def test_auto_trade_enabled_is_rejected(self):
        with self.assertRaises(ConfigError):
            load_config({"AUTO_TRADE_ENABLED": "true"})

    def test_remote_gui_host_is_rejected_for_phase_one(self):
        with self.assertRaises(ConfigError):
            load_config({"APP_HOST": "0.0.0.0"})

    def test_invalid_alert_thresholds_are_rejected(self):
        with self.assertRaises(ConfigError):
            load_config({"MIN_CONFIDENCE": "101"})
        with self.assertRaises(ConfigError):
            load_config({"ALERT_COOLDOWN_MINUTES": "-1"})
        with self.assertRaises(ConfigError):
            load_config({"MAX_ALERTS_PER_SYMBOL_PER_DAY": "0"})

    def test_telegram_credentials_are_read_from_environment(self):
        config = load_config({"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"})

        self.assertTrue(config.telegram.configured)
        self.assertEqual(config.telegram.bot_token, "token")
        self.assertEqual(config.telegram.chat_id, "chat")

    def test_explicit_app_config_rejects_auto_trade(self):
        with self.assertRaises(ConfigError):
            AppConfig(auto_trade_enabled=True)


if __name__ == "__main__":
    unittest.main()

