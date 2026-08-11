"""
Backward compatibility bridge for telegram_bot.py.
Points directly to the production-grade telegram subpackage.
"""
from autonomous_media.services.telegram import telegram_notifier, TelegramNotifierService

__all__ = ["telegram_notifier", "TelegramNotifierService"]
