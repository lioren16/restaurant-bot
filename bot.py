import sqlite3
import asyncio
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- DB ----------------
conn = sqlite3.connect("menu.db", check_same_thread=False)
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
    items TEXT,
    time TEXT
)
""")

conn.commit()

ADMIN_ID = 1767504481

# ---------------- MEMORY ----------------
cart = {}
add_state = {}

# ---------------- KEYBOARDS ----------------
def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🍽 Меню")
    kb.button(text="🛒 Корзина")
    kb.button(text="📦 Оформить заказ")
    kb.button(text="👤 Админка")
    kb.adjust(2)
    return kb.as_markup()


def admin_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="➕ Добавить блюдо")
    kb.button(text="📦 Заказы")
    kb.button(text="⬅ Назад")
    kb.adjust(1)
    return kb.as_markup()

# ---------------- START ----------------
@dp.message(CommandStart())
async def start(msg: Message):
    cart[msg.from_user.id] = []
    await msg.answer("🍽 Добро пожаловать!", reply_markup=main_kb())

# ---------------- MENU ----------------
@dp.message(F.text == "🍽 Меню")
async def menu(msg: Message):
    cur.execute("SELECT DISTINCT category FROM dishes")
    cats = cur.fetchall()

    if not cats:
        return await msg.answer("Категорий нет")

    kb = InlineKeyboardBuilder()

    for c in cats:
        kb.button(text=c[0], callback_data=f"cat_{c[0]}")

    kb.adjust(2)

    await msg.answer("Выберите категорию 👇", reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("cat_"))
async def show_cat(call: CallbackQuery):
    cat = call.data.replace("cat_", "")

    cur.execute("SELECT id, name, photo FROM dishes WHERE category=?", (cat,))
    items = cur.fetchall()

    if not items:
        return await call.message.answer("Пусто")

    for dish_id, name, photo in items:
        kb = InlineKeyboardBuilder()
        kb.button(text="➕ В корзину", callback_data=f"add_{dish_id}")

        await call.message.answer_photo(photo, caption=name, reply_markup=kb.as_markup())

# ---------------- CART ----------------
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(call: CallbackQuery):
    dish_id = int(call.data.replace("add_", ""))

    cur.execute("SELECT name FROM dishes WHERE id=?", (dish_id,))
    row = cur.fetchone()

    if not row:
        return await call.answer("Ошибка")

    name = row[0]

    uid = call.from_user.id
    cart.setdefault(uid, []).append(name)

    await call.answer("Добавлено в корзину ✅")


@dp.message(F.text == "🛒 Корзина")
async def show_cart(msg: Message):
    items = cart.get(msg.from_user.id, [])

    if not items:
        return await msg.answer("Корзина пустая")

    text = "🛒 Ваша корзина:\n\n"
    text += "\n".join([f"• {i}" for i in items])

    await msg.answer(text)

# ---------------- ORDER ----------------
@dp.message(F.text == "📦 Оформить заказ")
async def make_order(msg: Message):
    uid = msg.from_user.id
    items = cart.get(uid, [])

    if not items:
        return await msg.answer("Корзина пустая")

    time = datetime.now().strftime("%Y-%m-%d %H:%M")

    cur.execute(
        "INSERT INTO orders (user_id, username, items, time) VALUES (?, ?, ?, ?)",
        (uid, msg.from_user.username or "no_username", ", ".join(items), time)
    )
    conn.commit()

    cart[uid] = []

    await msg.answer("✅ Заказ оформлен!")

# ---------------- ADMIN ----------------
@dp.message(F.text == "👤 Админка")
async def admin(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer("👨‍💼 Админ панель", reply_markup=admin_kb())


@dp.message(F.text == "⬅ Назад")
async def back(msg: Message):
    await msg.answer("Главное меню", reply_markup=main_kb())

# ---------------- ADD DISH (FIXED FSM WITHOUT CONFLICTS) ----------------
@dp.message(F.text == "➕ Добавить блюдо")
async def add_start(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    add_state[msg.from_user.id] = {"step": "photo"}
    await msg.answer("Отправь фото блюда 📸")


@dp.message(F.photo)
async def add_photo(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    if msg.from_user.id not in add_state:
        return

    add_state[msg.from_user.id]["photo"] = msg.photo[-1].file_id
    add_state[msg.from_user.id]["step"] = "name"

    await msg.answer("Теперь отправь название блюда")


# ⚠️ ВАЖНО: УБРАЛИ ГЛОБАЛЬНЫЙ ПЕРЕХВАТ
@dp.message(F.from_user.id == ADMIN_ID)
async def admin_input_router(msg: Message):
    uid = msg.from_user.id

    if uid not in add_state:
        return

    state = add_state[uid]
    text = (msg.text or "").strip()

    blocked = ["👤 Админка", "📦 Заказы", "⬅ Назад", "➕ Добавить блюдо"]
    if text in blocked:
        return

    if state["step"] == "name":
        state["name"] = text
        state["step"] = "category"
        await msg.answer("Отправь категорию")
        return

    if state["step"] == "category":
        cur.execute(
            "INSERT INTO dishes (name, category, photo) VALUES (?, ?, ?)",
            (state["name"], text, state["photo"])
        )
        conn.commit()

        add_state.pop(uid, None)

        await msg.answer("Добавлено ✅")

# ---------------- ORDERS ----------------
@dp.message(F.text == "📦 Заказы")
async def orders(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    cur.execute("SELECT user_id, username, items, time FROM orders ORDER BY id DESC")
    data = cur.fetchall()

    if not data:
        return await msg.answer("Нет заказов")

    text = "📦 ЗАКАЗЫ:\n\n"

    for uid, user, items, time in data:
        text += f"👤 {user} ({uid})\n🕒 {time}\n🧾 {items}\n\n"

    await msg.answer(text)

# ---------------- RUN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
