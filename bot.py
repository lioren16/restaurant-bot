import sqlite3
import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- DB ----------------
conn = sqlite3.connect("menu.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    category TEXT,
    photo TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    items TEXT
)
""")

conn.commit()

ADMIN_ID = 1767504481

# ---------------- KEYBOARDS ----------------
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🍽 Меню")
    kb.button(text="🛒 Оформить заказ")
    kb.button(text="👤 Админка")
    kb.adjust(2)
    return kb.as_markup()


def admin_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="➕ Добавить блюдо")
    kb.button(text="📦 Заказы")
    kb.button(text="⬅ Назад")
    kb.adjust(1)
    return kb.as_markup()


# ---------------- START ----------------
@dp.message(CommandStart())
async def start(msg: Message):
    await msg.answer("Добро пожаловать 🍽", reply_markup=main_menu())


# ---------------- MENU ----------------
@dp.message(F.text == "🍽 Меню")
async def menu(msg: Message):
    cur.execute("SELECT DISTINCT category FROM dishes")
    cats = cur.fetchall()

    if not cats:
        return await msg.answer("Категорий пока нет")

    kb = InlineKeyboardBuilder()

    for c in cats:
        kb.button(text=c[0], callback_data=f"cat_{c[0]}")

    kb.adjust(2)

    await msg.answer("Выберите категорию 👇", reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("cat_"))
async def show_cat(call: CallbackQuery):
    cat = call.data.replace("cat_", "")

    cur.execute("SELECT name, photo FROM dishes WHERE category=?", (cat,))
    items = cur.fetchall()

    if not items:
        return await call.message.answer("В этой категории пока пусто")

    for name, photo in items:
        await call.message.answer_photo(photo, caption=name)


# ---------------- ORDER SYSTEM ----------------
ORDER_STATE = {}


@dp.message(F.text == "🛒 Оформить заказ")
async def start_order(msg: Message):
    ORDER_STATE[msg.from_user.id] = True
    await msg.answer("Напиши, что хочешь заказать 🧾")


@dp.message()
async def save_order(msg: Message):
    text = (msg.text or "").lower()

    # игнор кнопок меню
    if text in ["🍽 меню", "🛒 оформить заказ", "👤 админка", "⬅ назад", "➕ добавить блюдо", "📦 заказы"]:
        return

    if text.startswith("/"):
        return

    # если пользователь не в режиме заказа
    if not ORDER_STATE.get(msg.from_user.id):
        return

    ORDER_STATE[msg.from_user.id] = False

    cur.execute(
        "INSERT INTO orders (user_id, username, items) VALUES (?, ?, ?)",
        (msg.from_user.id, msg.from_user.username or "no_username", msg.text)
    )
    conn.commit()

    await msg.answer("Заказ принят ✅")


# ---------------- ADMIN ----------------
@dp.message(F.text == "👤 Админка")
async def admin(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    await msg.answer("Админ панель:", reply_markup=admin_menu())


@dp.message(F.text == "⬅ Назад")
async def back(msg: Message):
    await msg.answer("Главное меню", reply_markup=main_menu())


# ---------------- ADD DISH ----------------
add_state = {}


@dp.message(F.text == "➕ Добавить блюдо")
async def add_start(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    add_state[msg.from_user.id] = {}
    await msg.answer("Отправь фото блюда 📸")


@dp.message(F.photo)
async def get_photo(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    file_id = msg.photo[-1].file_id
    add_state[msg.from_user.id]["photo"] = file_id

    await msg.answer("Теперь отправь название блюда")


@dp.message()
async def get_name(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    if msg.from_user.id not in add_state:
        return

    if "photo" not in add_state[msg.from_user.id]:
        return

    add_state[msg.from_user.id]["name"] = msg.text
    await msg.answer("Теперь отправь категорию")


@dp.message()
async def get_category(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    if msg.from_user.id not in add_state:
        return

    data = add_state[msg.from_user.id]

    if "photo" not in data or "name" not in data:
        return

    cur.execute(
        "INSERT INTO dishes (name, category, photo) VALUES (?, ?, ?)",
        (data["name"], msg.text, data["photo"])
    )
    conn.commit()

    add_state.pop(msg.from_user.id)

    await msg.answer("Блюдо добавлено ✅")


# ---------------- ORDERS VIEW ----------------
@dp.message(F.text == "📦 Заказы")
async def orders(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    cur.execute("SELECT user_id, username, items FROM orders ORDER BY id DESC LIMIT 10")
    data = cur.fetchall()

    if not data:
        return await msg.answer("Заказов нет")

    text = "📦 Последние заказы:\n\n"

    for uid, username, items in data:
        text += f"👤 {username}\n🧾 {items}\n\n"

    await msg.answer(text)


# ---------------- RUN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
