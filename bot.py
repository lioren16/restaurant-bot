import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8856974231:AAFaZe8v1pFGTa420RvjTmfpKfo0_Pxkt04"
ADMIN_ID = 1767504481

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- DATABASE ----------------
conn = sqlite3.connect("database.db")
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
CREATE TABLE IF NOT EXISTS cart (
    user_id INTEGER,
    dish_id INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    items TEXT
)
""")

conn.commit()

# ---------------- CATEGORIES ----------------
CATEGORIES = [
    "Завтраки",
    "Пасты",
    "Второе",
    "Супы",
    "Салаты",
    "Бургеры",
    "Напитки"
]

# ---------------- KEYBOARDS ----------------
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍽 Меню")],
            [KeyboardButton(text="🛒 Корзина")],
            [KeyboardButton(text="👨‍🍳 Админка")]
        ],
        resize_keyboard=True
    )

def categories_kb():
    kb = [[InlineKeyboardButton(text=c, callback_data=f"cat_{c}")] for c in CATEGORIES]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить блюдо")],
            [KeyboardButton(text="📦 Заказы")],
            [KeyboardButton(text="⬅ Назад")]
        ],
        resize_keyboard=True
    )

# ---------------- START ----------------
@dp.message(F.text == "/start")
async def start(msg: Message):
    await msg.answer("🍽 Добро пожаловать в ресторан!", reply_markup=main_menu())

# ---------------- MENU ----------------
@dp.message(F.text == "🍽 Меню")
async def menu(msg: Message):
    await msg.answer("Выберите категорию:", reply_markup=categories_kb())

# ---------------- CATEGORY ----------------
@dp.callback_query(F.data.startswith("cat_"))
async def show_category(call: CallbackQuery):
    cat = call.data.replace("cat_", "")

    cur.execute("SELECT id, name, photo FROM dishes WHERE category=?", (cat,))
    dishes = cur.fetchall()

    if not dishes:
        await call.message.answer("В этой категории пока пусто 😕")
        return

    for dish_id, name, photo in dishes:

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ В корзину", callback_data=f"add_{dish_id}")]
        ])

        if photo:
            await bot.send_photo(call.message.chat.id, photo, caption=name, reply_markup=kb)
        else:
            await call.message.answer(name, reply_markup=kb)

# ---------------- ADD TO CART ----------------
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(call: CallbackQuery):
    dish_id = int(call.data.replace("add_", ""))

    cur.execute("INSERT INTO cart VALUES (?,?)", (call.from_user.id, dish_id))
    conn.commit()

    await call.answer("Добавлено в корзину ✅")

# ---------------- CART ----------------
@dp.message(F.text == "🛒 Корзина")
async def cart(msg: Message):
    cur.execute("SELECT dish_id FROM cart WHERE user_id=?", (msg.from_user.id,))
    items = cur.fetchall()

    if not items:
        await msg.answer("Корзина пуста 🛒")
        return

    dish_ids = [i[0] for i in items]

    text = "🛒 Ваш заказ:\n\n"
    for did in dish_ids:
        cur.execute("SELECT name FROM dishes WHERE id=?", (did,))
        r = cur.fetchone()
        if r:
            text += f"• {r[0]}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="order")]
    ])

    await msg.answer(text, reply_markup=kb)

# ---------------- ORDER ----------------
@dp.callback_query(F.data == "order")
async def order(call: CallbackQuery):
    cur.execute("SELECT dish_id FROM cart WHERE user_id=?", (call.from_user.id,))
    items = cur.fetchall()

    if not items:
        await call.message.answer("Корзина пуста")
        return

    dish_ids = [i[0] for i in items]

    names = []
    for did in dish_ids:
        cur.execute("SELECT name FROM dishes WHERE id=?", (did,))
        r = cur.fetchone()
        if r:
            names.append(r[0])

    order_text = "\n".join(names)

    cur.execute(
        "INSERT INTO orders (user_id, items) VALUES (?,?)",
        (call.from_user.id, order_text)
    )
    conn.commit()

    cur.execute("DELETE FROM cart WHERE user_id=?", (call.from_user.id,))
    conn.commit()

    await call.message.answer("Заказ оформлен ✅")

    await bot.send_message(
        ADMIN_ID,
        f"🔥 Новый заказ:\n\n{order_text}"
    )

# ---------------- ADMIN ----------------
@dp.message(F.text == "👨‍🍳 Админка")
async def admin(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer("👨‍🍳 Админ панель", reply_markup=admin_kb())

@dp.message(F.text == "⬅ Назад")
async def back(msg: Message):
    await msg.answer("Главное меню", reply_markup=main_menu())

# ---------------- ORDERS (UPDATED WITH USER INFO) ----------------
@dp.message(F.text == "📦 Заказы")
async def show_orders(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    cur.execute("SELECT user_id, items FROM orders ORDER BY id DESC")
    orders = cur.fetchall()

    if not orders:
        await msg.answer("Заказов пока нет 📭")
        return

    text = "📦 Все заказы:\n\n"

    for i, (user_id, items) in enumerate(orders, start=1):

        try:
            user = await bot.get_chat(user_id)
            name = user.full_name
            username = f"@{user.username}" if user.username else "нет username"
        except:
            name = "не найден"
            username = "нет"

        text += (
            f"🧾 Заказ #{i}\n"
            f"👤 Имя: {name}\n"
            f"🔗 Username: {username}\n"
            f"🆔 ID: {user_id}\n"
            f"🍽 Состав:\n{items}\n"
            f"──────────────────\n\n"
        )

    await msg.answer(text)

# ---------------- ADD DISH FLOW ----------------
user_state = {}

@dp.message(F.text == "➕ Добавить блюдо")
async def add_start(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    user_state[msg.from_user.id] = {"step": "name"}
    await msg.answer("Введите название блюда:")

@dp.message()
async def add_flow(msg: Message):
    uid = msg.from_user.id

    if uid not in user_state:
        return

    step = user_state[uid]["step"]

    if step == "name":
        user_state[uid]["name"] = msg.text
        user_state[uid]["step"] = "category"
        await msg.answer("Введите категорию:\n" + ", ".join(CATEGORIES))

    elif step == "category":
        user_state[uid]["category"] = msg.text
        user_state[uid]["step"] = "photo"
        await msg.answer("Отправь фото блюда")

    elif step == "photo":
        if not msg.photo:
            await msg.answer("Нужно фото!")
            return

        file_id = msg.photo[-1].file_id

        cur.execute(
            "INSERT INTO dishes (name, category, photo) VALUES (?,?,?)",
            (user_state[uid]["name"], user_state[uid]["category"], file_id)
        )
        conn.commit()

        user_state.pop(uid)

        await msg.answer("Блюдо добавлено ✅")

# ---------------- RUN ----------------
async def main():
    await dp.start_polling(bot)

import os
from aiohttp import web

async def handle(request):
    return web.Response(text="Bot is running")

app = web.Application()
app.router.add_get("/", handle)

async def run_web():
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

if __name__ == "__main__":
    asyncio.run(main())
