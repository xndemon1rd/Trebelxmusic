"""TrabelxMusic Economy, Coins, Membership, VIP and Telegram Stars store."""
from datetime import datetime, timezone, timedelta
import re

from pyrogram import filters
from pyrogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice,
    Message, PreCheckoutQuery,
)

import config
from TrabelxMusic import app
from TrabelxMusic.utils.database import (
    add_coins, buy_extra_download, claim_daily_reward, claim_weekly_reward,
    ensure_economy_user, get_banner, get_coins, get_download_status,
    get_economy, get_group_referral, get_referrer, is_member, is_vip,
    mark_payment_paid, payment_already_processed, record_group_referral,
    force_remove_coins, remove_coins, set_banner, set_membership, set_vip, set_referrer, set_user_banner,
)
from config import BANNED_USERS, OWNER_ID

DAILY_BASE = 100
WEEKLY_BASE = 300
REFERRAL_REWARD = 1000
EXTRA_DOWNLOAD_COST = int(getattr(config, "DOWNLOAD_EXTRA_COST_COINS", 100))

COIN_PACKS = {
    "coins10k": (10_000, 50),
    "coins50k": (50_000, 200),
    "coins100k": (100_000, 500),
}
VIP_PACKS = {
    "vip1m": (30, 50),
    "vip3m": (90, 200),
    "vip6m": (180, 400),
    "vip1y": (365, 600),
}
MEMBERSHIP_PACKS = {
    "mem1m": (30, 2_000, 25),
    "mem3m": (90, 6_000, 50),
    "mem6m": (180, 10_000, 100),
    "mem1y": (365, 15_000, 200),
}

def _now():
    return datetime.now(timezone.utc)

def _extra_percent(data):
    vip_until = data.get("vip_until")
    if vip_until and vip_until > _now():
        return 5
    mem_until = data.get("membership_until")
    if mem_until and mem_until > _now():
        return 1
    return 0

def _reward(base, percent):
    return int(base * (100 + percent) / 100)

def _menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 Coins", callback_data="eco:coins"),
         InlineKeyboardButton("👑 VIP", callback_data="eco:vip")],
        [InlineKeyboardButton("💎 Membership", callback_data="eco:mem"),
         InlineKeyboardButton("🛍 Store", callback_data="eco:store")],
        [InlineKeyboardButton("🎨 My Profile", callback_data="eco:profile")],
    ])

def _store():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 10,000 — ⭐50", callback_data="eco:buy:coins10k"),
         InlineKeyboardButton("🪙 50,000 — ⭐200", callback_data="eco:buy:coins50k")],
        [InlineKeyboardButton("🪙 100,000 — ⭐500", callback_data="eco:buy:coins100k")],
        [InlineKeyboardButton("👑 VIP 1M — ⭐50", callback_data="eco:buy:vip1m"),
         InlineKeyboardButton("👑 VIP 3M — ⭐200", callback_data="eco:buy:vip3m")],
        [InlineKeyboardButton("👑 VIP 6M — ⭐400", callback_data="eco:buy:vip6m"),
         InlineKeyboardButton("👑 VIP 1Y — ⭐600", callback_data="eco:buy:vip1y")],
        [InlineKeyboardButton("💎 Mem 1M — 2,000🪙 / ⭐25", callback_data="eco:buy:mem1m")],
        [InlineKeyboardButton("💎 Mem 3M — 6,000🪙 / ⭐50", callback_data="eco:buy:mem3m")],
        [InlineKeyboardButton("💎 Mem 6M — 10,000🪙 / ⭐100", callback_data="eco:buy:mem6m")],
        [InlineKeyboardButton("💎 Mem 1Y — 15,000🪙 / ⭐200", callback_data="eco:buy:mem1y")],
    ])

async def _invoice(chat_id, payload, title, description, stars):
    # Telegram Stars digital-goods invoices use currency XTR and require no
    # external payment provider. A successful_payment update is required before
    # granting the purchased item.
    await app.send_invoice(
        chat_id=chat_id,
        title=title[:32],
        description=description[:255],
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=title[:32], amount=int(stars))],
    )

async def _apply_stars_purchase(user_id, payload, stars, charge_id):
    if await payment_already_processed(charge_id):
        return "already"
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != "trabelx":
        return "invalid"

    product = parts[1]
    plan = parts[2]
    data = await get_economy(user_id)

    if product == "coins" and plan in COIN_PACKS:
        coins, expected = COIN_PACKS[plan]
        if stars != expected:
            return "invalid"
        grant = coins
        await add_coins(user_id, grant, "stars_coins")
        await mark_payment_paid(payload, charge_id)
        return f"🪙 Added <b>{grant:,}</b> coins."

    if product == "vip" and plan in VIP_PACKS:
        days, expected = VIP_PACKS[plan]
        if stars != expected:
            return "invalid"
        current = data.get("vip_until")
        start = current if current and current > _now() else _now()
        await set_vip(user_id, start + timedelta(days=days))
        await mark_payment_paid(payload, charge_id)
        return f"👑 VIP activated for <b>{days} days</b>."

    if product == "mem" and plan in MEMBERSHIP_PACKS:
        days, coin_price, expected = MEMBERSHIP_PACKS[plan]
        if stars != expected:
            return "invalid"
        current = data.get("membership_until")
        start = current if current and current > _now() else _now()
        await set_membership(user_id, start + timedelta(days=days))
        await mark_payment_paid(payload, charge_id)
        return f"💎 Membership activated for <b>{days} days</b>."

    return "invalid"

@app.on_message(filters.command(["coins", "economy", "wallet", "shop", "store"]) & filters.private & ~BANNED_USERS)
async def economy_command(_, message: Message):
    user_id = message.from_user.id
    await ensure_economy_user(user_id)
    data = await get_economy(user_id)
    status = await get_download_status(user_id)
    percent = _extra_percent(data)
    vip = "ON" if status["vip"] else "OFF"
    mem = "ON" if status["membership"] else "OFF"
    limit = "∞" if status["limit"] is None else str(status["limit"])
    await message.reply_text(
        f"🪙 <b>Trabelx Economy</b>\n\n"
        f"💰 Coins: <b>{data.get('coins', 0):,}</b>\n"
        f"📥 Downloads: <b>{status['used']}/{limit}</b>\n"
        f"👑 VIP: <b>{vip}</b>\n"
        f"💎 Membership: <b>{mem}</b>\n"
        f"✨ Reward bonus: <b>+{percent}%</b>\n\n"
        f"Daily: {DAILY_BASE} coins • Weekly: {WEEKLY_BASE} coins\n"
        f"Referral: {REFERRAL_REWARD} coins when the referred user adds the bot to a group.",
        reply_markup=_menu(),
    )

@app.on_message(filters.command(["daily"]) & filters.private & ~BANNED_USERS)
async def daily_command(_, message: Message):
    user_id = message.from_user.id
    data = await get_economy(user_id)
    amount = _reward(DAILY_BASE, _extra_percent(data))
    got = await claim_daily_reward(user_id, amount)
    await message.reply_text(
        f"🎁 Daily reward: <b>+{got or 0} coins</b>.\n"
        + ("Come back tomorrow for another reward." if got else "You already claimed today's reward.")
    )

@app.on_message(filters.command(["weekly"]) & filters.private & ~BANNED_USERS)
async def weekly_command(_, message: Message):
    user_id = message.from_user.id
    data = await get_economy(user_id)
    amount = _reward(WEEKLY_BASE, _extra_percent(data))
    got = await claim_weekly_reward(user_id, amount)
    await message.reply_text(
        f"🎁 Weekly reward: <b>+{got or 0} coins</b>.\n"
        + ("Come back next week for another reward." if got else "You already claimed this week's reward.")
    )

@app.on_message(filters.command(["referral", "refer", "ref"]) & filters.private & ~BANNED_USERS)
async def referral_command(_, message: Message):
    me = await app.get_me()
    link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"
    await message.reply_text(
        f"🔗 <b>Your referral link</b>\n\n<code>{link}</code>\n\n"
        f"🎁 You receive <b>{REFERRAL_REWARD:,} coins</b> when a referred user starts the bot and then adds it to a group."
    )

@app.on_message(filters.command(["profile"]) & filters.private & ~BANNED_USERS)
async def profile_command(_, message: Message):
    await _send_profile(message.chat.id, message.from_user.id)

async def _send_profile(chat_id, user_id):
    data = await get_economy(user_id)
    status = await get_download_status(user_id)
    banner = None
    if status["vip"]:
        banner = await get_user_banner(user_id)
    if not banner and status["membership"]:
        banner = await get_banner(1) or await get_banner(2)
    text = (
        f"🎧 <b>Trabelx Profile</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"🪙 Coins: <b>{data.get('coins', 0):,}</b>\n"
        f"📥 Downloads: <b>{status['used']}/{'∞' if status['limit'] is None else status['limit']}</b>\n"
        f"💎 Membership: <b>{'ACTIVE' if status['membership'] else 'OFF'}</b>\n"
        f"👑 VIP: <b>{'ACTIVE' if status['vip'] else 'OFF'}</b>\n"
        f"✨ Reward bonus: <b>+{_extra_percent(data)}%</b>"
    )
    if banner:
        return await app.send_photo(chat_id, banner, caption=text, reply_markup=_menu())
    return await app.send_message(chat_id, text, reply_markup=_menu())

@app.on_callback_query(filters.regex(r"^eco:") & ~BANNED_USERS)
async def economy_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    data = await get_economy(user_id)
    action = query.data.split(":")
    try:
        await query.answer()
    except Exception:
        pass

    if action[1] == "store":
        return await query.message.edit_text("🛍 <b>Trabelx Store</b>\n\nChoose a package:", reply_markup=_store())

    if action[1] == "coins":
        return await query.message.edit_text(
            f"🪙 <b>Coins</b>\n\nBalance: <b>{data.get('coins',0):,}</b>\n"
            f"Daily: +{_reward(DAILY_BASE, _extra_percent(data))}\n"
            f"Weekly: +{_reward(WEEKLY_BASE, _extra_percent(data))}\n"
            f"Extra download: <b>{EXTRA_DOWNLOAD_COST} coins</b>.",
            reply_markup=_store(),
        )

    if action[1] == "vip":
        return await query.message.edit_text(
            "👑 <b>VIP</b>\n\n"
            "• +5% daily/weekly/referral rewards\n"
            "• Unlimited downloads\n"
            "• Choose your own profile banner\n\n"
            "1M ⭐50 • 3M ⭐200 • 6M ⭐400 • 1Y ⭐600",
            reply_markup=_store(),
        )

    if action[1] == "mem":
        return await query.message.edit_text(
            "💎 <b>Membership</b>\n\n"
            "• +1% daily/weekly/referral rewards\n"
            "• 15 downloads/day\n"
            "• Member profile banner\n\n"
            "1M 2,000🪙/⭐25 • 3M 6,000🪙/⭐50\n"
            "6M 10,000🪙/⭐100 • 1Y 15,000🪙/⭐200",
            reply_markup=_store(),
        )

    if action[1] == "profile":
        await query.message.delete()
        return await _send_profile(user_id, user_id)

    if action[1] == "buy" and len(action) == 3:
        plan = action[2]
        if plan in COIN_PACKS:
            coins, stars = COIN_PACKS[plan]
            payload = f"trabelx:coins:{plan}"
            await _invoice(user_id, payload, f"{coins:,} Coins", f"Purchase {coins:,} Trabelx coins.", stars)
            return

        if plan in VIP_PACKS:
            days, stars = VIP_PACKS[plan]
            payload = f"trabelx:vip:{plan}"
            await _invoice(user_id, payload, f"VIP {days} Days", f"Trabelx VIP for {days} days.", stars)
            return

        if plan in MEMBERSHIP_PACKS:
            days, coin_price, stars = MEMBERSHIP_PACKS[plan]
            if data.get("coins", 0) >= coin_price:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🪙 Buy with {coin_price:,} coins", callback_data=f"eco:memcoin:{plan}")],
                    [InlineKeyboardButton(f"⭐ Buy with {stars} Stars", callback_data=f"eco:memstars:{plan}")],
                ])
                return await query.message.edit_text(
                    f"💎 <b>Membership {days} days</b>\nChoose payment method:",
                    reply_markup=kb,
                )
            await _invoice(user_id, f"trabelx:mem:{plan}", f"Membership {days} Days", f"Trabelx Membership for {days} days.", stars)
            return

    if action[1] == "memcoin" and len(action) == 3 and action[2] in MEMBERSHIP_PACKS:
        plan = action[2]
        days, coin_price, stars = MEMBERSHIP_PACKS[plan]
        if not await remove_coins(user_id, coin_price, "membership"):
            return await query.answer("Not enough coins.", show_alert=True)
        current = data.get("membership_until")
        start = current if current and current > _now() else _now()
        await set_membership(user_id, start + timedelta(days=days))
        return await query.message.edit_text(f"💎 Membership activated for <b>{days} days</b> using {coin_price:,} coins.")

    if action[1] == "memstars" and len(action) == 3 and action[2] in MEMBERSHIP_PACKS:
        days, coin_price, stars = MEMBERSHIP_PACKS[action[2]]
        return await _invoice(user_id, f"trabelx:mem:{action[2]}", f"Membership {days} Days", f"Trabelx Membership for {days} days.", stars)

@app.on_pre_checkout_query()
async def pre_checkout(_, query: PreCheckoutQuery):
    payload = query.invoice_payload
    parts = payload.split(":")
    valid = False
    expected = None
    if len(parts) == 3 and parts[0] == "trabelx":
        product, plan = parts[1], parts[2]
        if product == "coins" and plan in COIN_PACKS:
            expected = COIN_PACKS[plan][1]
        elif product == "vip" and plan in VIP_PACKS:
            expected = VIP_PACKS[plan][1]
        elif product == "mem" and plan in MEMBERSHIP_PACKS:
            expected = MEMBERSHIP_PACKS[plan][2]
        valid = expected == query.total_amount and query.currency == "XTR"
    await query.answer(ok=valid, error_message=None if valid else "This invoice is invalid or expired.")

@app.on_message(filters.private & ~BANNED_USERS)
async def successful_stars_payment(_, message: Message):
    payment = getattr(message, "successful_payment", None)
    if not payment:
        return
    if getattr(payment, "currency", None) != "XTR":
        return
    result = await _apply_stars_purchase(
        message.from_user.id,
        payment.invoice_payload,
        payment.total_amount,
        payment.telegram_payment_charge_id,
    )
    if result == "invalid":
        return await message.reply_text("⚠️ Payment received, but the invoice could not be verified. Contact the owner with your receipt.")
    await message.reply_text(f"✅ <b>Payment confirmed</b>\n\n{result}")

@app.on_message(filters.command(["setbanner1", "setbanner2"]) & filters.user(OWNER_ID))
async def owner_set_banner(_, message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text("Reply to a photo with /setbanner1 or /setbanner2.")
    slot = 1 if message.command[0].lower() == "setbanner1" else 2
    await set_banner(slot, message.reply_to_message.photo.file_id)
    await message.reply_text(f"✅ Membership banner {slot} saved.")

@app.on_message(filters.command(["setprofilebanner"]) & filters.private & ~BANNED_USERS)
async def set_vip_profile_banner(_, message: Message):
    if not await is_vip(message.from_user.id):
        return await message.reply_text("👑 This feature is available to VIP users.")
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text("Reply to a photo with /setprofilebanner.")
    await set_user_banner(message.from_user.id, message.reply_to_message.photo.file_id)
    await message.reply_text("✅ Your VIP profile banner has been saved.")

@app.on_chat_member_updated()
async def bot_membership_tracker(_, update):
    # Award the referral only when the bot is actually added to a group.
    chat = update.chat
    new_member = update.new_chat_member
    old_member = update.old_chat_member
    if not chat or not new_member:
        return
    if getattr(new_member, "user", None) is None or new_member.user.id != app.id:
        return

    new_status = str(getattr(new_member, "status", "")).lower()
    old_status = str(getattr(old_member, "status", "")).lower() if old_member else ""
    group_statuses = {"member", "administrator"}
    if new_status in group_statuses and old_status not in group_statuses:
        adder = getattr(update, "from_user", None)
        if not adder:
            return
        referred_by = await get_referrer(adder.id)
        if not referred_by:
            return
        if await record_group_referral(chat.id, referred_by, adder.id, _reward(REFERRAL_REWARD, _extra_percent(await get_economy(referred_by)))):
            data = await get_economy(referred_by)
            reward = _reward(REFERRAL_REWARD, _extra_percent(data))
            # The referral record stores the base reward. We add the actual
            # rewarded amount, so VIP/member bonus is also applied.
            await add_coins(referred_by, reward, "group_referral")
            try:
                await app.send_message(referred_by, f"🎉 Referral activated!\n\n+<b>{reward:,} coins</b> for the bot being added to a group.")
            except Exception:
                pass

    if new_status in {"left", "kicked"} and old_status in group_statuses:
        ref = await get_group_referral(chat.id)
        if ref and ref.get("active"):
            # Remove exactly the amount originally granted, not the current
            # bonus, so future reward changes cannot create an accounting mismatch.
            # The group record stores the exact amount that was awarded.
            await force_remove_coins(ref["inviter_id"], int(ref.get("reward", REFERRAL_REWARD)), "group_referral_removed")
