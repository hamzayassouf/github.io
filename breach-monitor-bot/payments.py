"""Subscription plan catalogue for Telegram Stars payments.

Prices are in Telegram Stars (currency code "XTR") — no external payment
provider account is needed for Stars, unlike classic fiat invoices.
Adjust freely; these numbers are placeholders until tested against real
willingness to pay.
"""

PLANS = {
    "individual": {
        "label": "فردي",
        "stars": 100,
        "days": 30,
        "email_limit": 1,
        "description": "مراقبة إيميل واحد باستمرار + تنبيه فوري عند أي تسريب جديد.",
    },
    "company": {
        "label": "شركات",
        "stars": 500,
        "days": 30,
        "email_limit": 10,
        "description": "مراقبة حتى 10 إيميلات (فريقك) باستمرار + تنبيه فوري عند أي تسريب جديد.",
    },
}
