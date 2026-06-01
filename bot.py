import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import sqlite3
from aiohttp import web

# ---------------- CONFIG ----------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# ---------------- DATABASE ----------------
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

# ---------------- CATEGORIES ----------------
categories = [
    "Завтраки",
    "Пасты",
    "Второе",
    "Супы",
    "Салаты",
    "Бургеры",
    "Напитки"
]

# ---------------- CART ----------------
cart = {}

# ---------------- KEYBOARD ----------------
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍽 Меню")],
            [KeyboardButton(text="🛒 Корзина")],
            [KeyboardButton(text="📦 Оформить заказ")],
            [KeyboardButton(text="👤 Админ")]
        ],
        resize_keyboard=True
    )

# ---------------- STATES ----------------
class AddDish(StatesGroup):
    name = State()
    category = State()
    photo = State()

# ---------------- START ----------------
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Добро пожаловать 🍽", reply_markup=main_kb())

# ---------------- ADMIN ----------------
@dp.message(F.text == "👤 Админ")
async def admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить блюдо", callback_data="add")],
        [InlineKeyboardButton(text="📦 Заказы", callback_data="orders")]
    ])

    await message.answer("Админ панель", reply_markup=kb)

# ---------------- ADD DISH ----------------
@dp.callback_query(F.data == "add")
async def add(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddDish.name)
    await call.message.answer("Название блюда:")

@dp.message(AddDish.name)
async def name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddDish.category)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in categories],
        resize_keyboard=True
    )

    await message.answer("Категория:", reply_markup=kb)

@dp.message(AddDish.category)
async def category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(AddDish.photo)
    await message.answer("Отправь фото блюда")

@dp.message(AddDish.photo, F.photo)
async def photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.photo[-1].file_id

    cur.execute(
        "INSERT INTO dishes (name, category, photo) VALUES (?, ?, ?)",
        (data["name"], data["category"], file_id)
    )
    conn.commit()

    await state.clear()
    await message.answer("Добавлено ✅", reply_markup=main_kb())

# ---------------- MENU ----------------
@dp.message(F.text == "🍽 Меню")
async def menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=c, callback_data=f"cat_{c}")] for c in categories]
    )
    await message.answer("Категории:", reply_markup=kb)

@dp.callback_query(F.data.startswith("cat_"))
async def show(call: types.CallbackQuery):
    cat = call.data.replace("cat_", "")

    cur.execute("SELECT id, name, photo FROM dishes WHERE category=?", (cat,))
    items = cur.fetchall()

    if not items:
        await call.message.answer("Пусто")
        return

    for i in items:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ В корзину", callback_data=f"add_{i[0]}")]
        ])

        await bot.send_photo(
            call.message.chat.id,
            photo=i[2],
            caption=i[1],
            reply_markup=kb
        )

# ---------------- CART ----------------
@dp.callback_query(F.data.startswith("add_"))
async def add_cart(call: types.CallbackQuery):
    dish_id = int(call.data.split("_")[1])

    cart.setdefault(call.from_user.id, [])
    cart[call.from_user.id].append(dish_id)

    await call.answer("Добавлено")

@dp.message(F.text == "🛒 Корзина")
async def show_cart(message: types.Message):
    items = cart.get(message.from_user.id, [])

    if not items:
        await message.answer("Пусто")
        return

    text = "Корзина:\n"

    for i in items:
        cur.execute("SELECT name FROM dishes WHERE id=?", (i,))
        n = cur.fetchone()
        if n:
            text += f"• {n[0]}\n"

    await message.answer(text)

# ---------------- ORDER ----------------
@dp.message(F.text == "📦 Оформить заказ")
async def order(message: types.Message):
    items = cart.get(message.from_user.id, [])

    if not items:
        await message.answer("Корзина пуста")
        return

    cur.execute("SELECT name FROM dishes WHERE id IN ({seq})".format(
        seq=",".join(["?"] * len(items))
    ), items)

    names = cur.fetchall()
    order_text = "\n".join([n[0] for n in names])

    cur.execute(
        "INSERT INTO orders (user_id, username, items) VALUES (?, ?, ?)",
        (message.from_user.id, message.from_user.username, order_text)
    )
    conn.commit()

    await bot.send_message(
        ADMIN_ID,
        f"📦 ЗАКАЗ\n\n👤 @{message.from_user.username}\n\n{order_text}"
    )

    cart[message.from_user.id] = []

    await message.answer("Заказ оформлен ✅")

# ---------------- ORDERS ----------------
@dp.callback_query(F.data == "orders")
async def orders(call: types.CallbackQuery):
    cur.execute("SELECT username, items FROM orders ORDER BY id DESC LIMIT 10")
    data = cur.fetchall()

    text = "Заказы:\n\n"

    for d in data:
        text += f"👤 @{d[0]}\n{d[1]}\n\n"

    await call.message.answer(text)

# ---------------- WEB SERVER (FIX RENDER PORT) ----------------
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

# ---------------- MAIN ----------------
async def main():
    await asyncio.gather(
        dp.start_polling(bot),
        run_web()
    )

if __name__ == "__main__":
    asyncio.run(main())
