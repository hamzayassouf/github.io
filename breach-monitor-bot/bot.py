"""Telegram bot: send an email, get back a breach report in Arabic.

Phase 1 — free single lookup per message, no accounts, no storage.
Phase 2 — paid subscriptions (Telegram Stars) for continuous monitoring
of one or more emails, with a daily job that re-checks them and alerts
on newly-appeared breaches.

Run with: python bot.py  (requires TELEGRAM_BOT_TOKEN in the environment)
"""

import asyncio
import logging
import os
import re
import time
from datetime import date, time as dtime, timezone

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

import db
from breach_check import check_email
from payments import PLANS

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs the full request URL at INFO level, which for the Telegram Bot
# API includes the bot token — keep it quiet so the token never hits stdout/logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

FREE_CHECK_COOLDOWN_SECONDS = 15
_last_free_check: dict[int, float] = {}

WELCOME_TEXT = (
    "أهلاً 👋\n\n"
    "أنا بوت بفحصلك إذا إيميلك ظهر بأي تسريب بيانات معروف.\n\n"
    "• ابعتلي إيميل مباشرة → فحص فوري ومجاني لمرة وحدة.\n"
    "• /subscribe → مراقبة مستمرة لإيميل واحد أو أكثر، وتنبيه فوري عند تسريب جديد.\n"
    "• /mystatus → شوف حالة اشتراكك.\n"
    "• /deletemydata → احذف كل بياناتك المخزّنة عندنا نهائياً.\n\n"
    "⚠️ الفحص المجاني لحظي وما منخزنه. المراقبة المستمرة بتتطلب اشتراك."
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

    chat_id = update.effective_chat.id
    now = time.monotonic()
    elapsed = now - _last_free_check.get(chat_id, 0.0)
    if elapsed < FREE_CHECK_COOLDOWN_SECONDS:
        wait = int(FREE_CHECK_COOLDOWN_SECONDS - elapsed) + 1
        await update.message.reply_text(f"⏳ استنى {wait} ثانية قبل ما تفحص إيميل تاني.")
        return
    _last_free_check[chat_id] = now

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
            "3️⃣ ما تعيد استخدام نفس كلمة السر بأكثر من موقع.\n\n"
            "بدك نراقبلك هالإيميل باستمرار؟ جرب /subscribe."
        )
    else:
        await update.message.reply_text(
            "✅ ما لقينا إيميلك بأي تسريب معروف حتى هلق.\n"
            "بس هاد ما بيعني حماية دائمة — تسريبات جديدة بتصير كل يوم.\n"
            "بدك نراقبلك هالإيميل باستمرار؟ جرب /subscribe."
        )


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [InlineKeyboardButton(f"{p['label']} — {p['stars']}⭐/شهر", callback_data=f"buyplan:{key}")]
        for key, p in PLANS.items()
    ]
    lines = "\n".join(f"• {p['label']}: {p['description']}" for p in PLANS.values())
    await update.message.reply_text(f"اختر خطتك:\n\n{lines}", reply_markup=InlineKeyboardMarkup(buttons))


async def handle_plan_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    plan_key = query.data.split(":", 1)[1]
    plan = PLANS.get(plan_key)
    if not plan:
        return

    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=f"اشتراك {plan['label']} — مراقبة تسريبات شهرية",
        description=plan["description"],
        payload=plan_key,
        currency="XTR",
        prices=[LabeledPrice(plan["label"], plan["stars"])],
        # provider_token must be omitted (not "") for Telegram Stars —
        # passing an empty string triggers PROVIDER_ACCOUNT_INVALID.
    )


async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload not in PLANS:
        await query.answer(ok=False, error_message="خطة غير معروفة، جرب /subscribe من جديد.")
    else:
        await query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    plan_key = payment.invoice_payload
    plan = PLANS[plan_key]
    chat_id = update.effective_chat.id
    expiry = db.upsert_subscription(chat_id, plan_key, plan["days"])
    await update.message.reply_text(
        f"✅ تم تفعيل اشتراك {plan['label']} لغاية {expiry}.\n\n"
        f"هلق ابعتلي الإيميل (لحد {plan['email_limit']} إيميل) يلي بدك نراقبه بالأمر:\n"
        "/watch email@example.com"
    )


async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    sub = db.get_subscription(chat_id)
    if not sub or not sub["active"]:
        await update.message.reply_text("لازم يكون عندك اشتراك فعّال أول. جرب /subscribe.")
        return

    if not context.args:
        await update.message.reply_text("استخدم هيك: /watch email@example.com")
        return

    email = context.args[0].strip()
    if not EMAIL_RE.match(email):
        await update.message.reply_text("هاد مش شكل إيميل صحيح 🤔")
        return

    current = db.list_watched_emails(chat_id)
    if email in current:
        await update.message.reply_text("هاد الإيميل مراقَب أصلاً ✅")
        return

    limit = PLANS[sub["plan"]]["email_limit"]
    if len(current) >= limit:
        await update.message.reply_text(
            f"وصلت الحد الأقصى ({limit}) لخطتك. شيل إيميل بـ /unwatch حتى تضيف غيره."
        )
        return

    try:
        breaches = await asyncio.to_thread(check_email, email)
    except Exception:
        logger.exception("Breach lookup failed while adding a watch")
        await update.message.reply_text("صار خطأ أثناء الفحص الأولي، جرب كمان شوي 🙏")
        return

    db.add_watched_email(chat_id, email)
    db.update_last_breaches(chat_id, email, breaches)
    status = f"({len(breaches)} تسريب حالياً)" if breaches else "(ولا تسريب حالياً)"
    await update.message.reply_text(f"👁️ عم نراقب {email} {status}. رح تنبّهك أول ما يصير تسريب جديد.")


async def unwatch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("استخدم هيك: /unwatch email@example.com")
        return

    email = context.args[0].strip()
    if db.remove_watched_email(chat_id, email):
        await update.message.reply_text(f"تمام، وقفنا مراقبة {email}.")
    else:
        await update.message.reply_text("هاد الإيميل مش موجود بلستة المراقبة.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    sub = db.get_subscription(chat_id)
    if not sub:
        await update.message.reply_text("ما عندك اشتراك حالياً. جرب /subscribe.")
        return

    watched = db.list_watched_emails(chat_id)
    state = "فعّال ✅" if sub["active"] else "منتهي ⚠️"
    watched_list = "\n".join(f"• {e}" for e in watched) or "(ولا إيميل مراقَب بعد)"
    await update.message.reply_text(
        f"الخطة: {PLANS[sub['plan']]['label']}\n"
        f"الحالة: {state}\n"
        f"تاريخ الانتهاء: {sub['expires_at']}\n\n"
        f"الإيميلات المراقبة:\n{watched_list}"
    )


async def deletemydata_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "متأكد بدك تمسح كل بياناتك عندنا (الاشتراك وكل الإيميلات المراقبة)؟\n"
        "هاد الإجراء نهائي وما إله رجعة.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("نعم، امسح كل شي 🗑️", callback_data="confirmdelete")]]
        ),
    )


async def handle_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db.delete_user_data(query.message.chat_id)
    await query.edit_message_text("تم حذف كل بياناتك من عندنا. ✅")


async def check_watches_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    today = date.today().isoformat()
    for chat_id, _plan, expires_at, expiry_notified, email, last_breaches in db.all_watches_with_subscriptions():
        if expires_at < today:
            if not expiry_notified:
                try:
                    await context.bot.send_message(
                        chat_id, "⚠️ انتهى اشتراكك بمراقبة التسريبات. جدده عبر /subscribe حتى نكمل نراقبلك."
                    )
                except Exception:
                    logger.exception("Failed to send expiry notice")
                db.mark_expiry_notified(chat_id)
            continue

        try:
            current = await asyncio.to_thread(check_email, email)
        except Exception:
            logger.exception("Scheduled breach check failed")
            continue

        new_breaches = [b for b in current if b not in last_breaches]
        if new_breaches:
            breach_list = "\n".join(f"• {b}" for b in new_breaches)
            try:
                await context.bot.send_message(
                    chat_id,
                    f"🚨 تسريب جديد لـ {email}:\n\n{breach_list}\n\nغيّر كلمة السر فوراً!",
                )
            except Exception:
                logger.exception("Failed to send breach alert")
            db.update_last_breaches(chat_id, email, current)


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("لازم تحط TELEGRAM_BOT_TOKEN بملف .env (شوف .env.example)")

    db.init_db()

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("watch", watch_command))
    app.add_handler(CommandHandler("unwatch", unwatch_command))
    app.add_handler(CommandHandler("mystatus", status_command))
    app.add_handler(CommandHandler("deletemydata", deletemydata_command))
    app.add_handler(CallbackQueryHandler(handle_plan_choice, pattern=r"^buyplan:"))
    app.add_handler(CallbackQueryHandler(handle_delete_confirm, pattern=r"^confirmdelete$"))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_daily(check_watches_job, time=dtime(hour=9, tzinfo=timezone.utc))

    logger.info("Bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
