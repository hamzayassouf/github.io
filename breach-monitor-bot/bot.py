"""Telegram bot: send an email, get back a breach report in Arabic.

Phase 1 MVP — single free lookup per message, no accounts, no storage.
Run with: python bot.py  (requires TELEGRAM_BOT_TOKEN in the environment)
"""

import asyncio
import logging
import os
import re

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from breach_check import check_email

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs the full request URL at INFO level, which for the Telegram Bot
# API includes the bot token — keep it quiet so the token never hits stdout/logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

WELCOME_TEXT = (
    "أهلاً 👋\n\n"
    "أنا بوت بسيط بفحصلك إذا إيميلك ظهر بأي تسريب بيانات معروف.\n\n"
    "ابعتلي الإيميل يلي بدك تفحصه وبرجعلك التقرير خلال ثواني.\n\n"
    "⚠️ ما منخزن إيميلك أبداً — الفحص لحظي وبس."
)

HELP_TEXT = "ابعتلي إيميل صحيح متل: name@example.com وبفحصلك ياه."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()

    if not EMAIL_RE.match(text):
        await update.message.reply_text(f"هاد مش شكل إيميل صحيح 🤔\n{HELP_TEXT}")
        return

    await update.message.reply_text("⏳ عم فحص الإيميل...")

    try:
        breaches = await asyncio.to_thread(check_email, text)
    except Exception:
        logger.exception("Breach lookup failed")
        await update.message.reply_text("صار خطأ أثناء الفحص، جرب كمان شوي 🙏")
        return

    if breaches:
        breach_list = "\n".join(f"• {name}" for name in breaches)
        await update.message.reply_text(
            f"🚨 لقينا إيميلك بـ {len(breaches)} تسريب/تسريبات معروفة:\n\n"
            f"{breach_list}\n\n"
            "شو لازم تعمل:\n"
            "1️⃣ غيّر كلمة السر لهاد الإيميل وأي حساب فيه نفس كلمة السر.\n"
            "2️⃣ فعّل التحقق بخطوتين (2FA) إذا مش مفعّل.\n"
            "3️⃣ ما تعيد استخدام نفس كلمة السر بأكثر من موقع."
        )
    else:
        await update.message.reply_text(
            "✅ ما لقينا إيميلك بأي تسريب معروف حتى هلق.\n"
            "بس هاد ما بيعني حماية دائمة — تسريبات جديدة بتصير كل يوم."
        )


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("لازم تحط TELEGRAM_BOT_TOKEN بملف .env (شوف .env.example)")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
