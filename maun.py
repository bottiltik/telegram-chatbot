import os
import uvicorn
import asyncio
import random
from collections import defaultdict
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Update
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- Состояния для диалогов ---
class StudentForm(StatesGroup):
    waiting_for_name = State()      # добавление студента
    grade_name = State()            # ввод имени для оценки
    grade_value = State()           # ввод оценки

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Переменная TELEGRAM_BOT_TOKEN не найдена!")

WEBHOOK_URL = "telegram-chatbot-production-274b6c97.up.railway.app/webhook"  # замени на свой URL

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- База данных (пока в памяти) ---
# students = {"Аня": [5, 4, 5], "Игорь": [3, 4]}
students = defaultdict(list)

MIN_PASSING_AVG = 3.5  # порог для "зоны риска"

def average(grades):
    if not grades:
        return None
    return round(sum(grades) / len(grades), 2)

# --- Команды ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот анализа успеваемости 📊\n"
        "Напиши /help, чтобы увидеть список команд."
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Доступные команды:\n"
        "/add — добавить студента\n"
        "/grade — поставить оценку студенту\n"
        "/list — список студентов со средним баллом\n"
        "/stats <имя> — статистика по студенту\n"
        "/top — трое лучших студентов\n"
        "/warning — студенты в зоне риска (средний балл < 3.5)"
    )

# --- Добавление студента ---
@dp.message(Command("add"))
async def cmd_add(message: types.Message, state: FSMContext):
    await state.set_state(StudentForm.waiting_for_name)
    await message.answer("Введите имя студента:")

@dp.message(StudentForm.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пришли имя обычным текстом.")
        return
    name = message.text.strip()
    if name in students:
        await message.answer(f"Студент «{name}» уже есть в системе.")
    else:
        students[name] = []
        await message.answer(f"Студент «{name}» добавлен! ✅\nТеперь можно ставить оценки командой /grade")
    await state.clear()

# --- Постановка оценки ---
@dp.message(Command("grade"))
async def cmd_grade(message: types.Message, state: FSMContext):
    if not students:
        await message.answer("Сначала добавьте студентов командой /add.")
        return
    await state.set_state(StudentForm.grade_name)
    await message.answer("Для кого ставим оценку? Введите имя студента:")

@dp.message(StudentForm.grade_name)
async def process_grade_name(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пришли имя обычным текстом.")
        return
    name = message.text.strip()
    if name not in students:
        await message.answer(f"Студент «{name}» не найден. Проверьте имя (/list) или добавьте через /add.")
        return
    await state.update_data(grade_name=name)
    await state.set_state(StudentForm.grade_value)
    await message.answer("Введите оценку от 2 до 5:")

@dp.message(StudentForm.grade_value)
async def process_grade_value(message: types.Message, state: FSMContext):
    if not message.text or not message.text.strip().lstrip("-").isdigit():
        await message.answer("Пожалуйста, введите целое число (оценку от 2 до 5).")
        return
    grade = int(message.text.strip())
    if grade < 2 or grade > 5:
        await message.answer("Оценка должна быть от 2 до 5. Попробуйте ещё раз:")
        return
    data = await state.get_data()
    name = data.get("grade_name")
    students[name].append(grade)
    avg = average(students[name])
    await message.answer(
        f"Оценка {grade} поставлена студенту «{name}» ✅\n"
        f"Текущий средний балл: {avg} (оценок: {len(students[name])})"
    )
    await state.clear()

# --- Список студентов ---
@dp.message(Command("list"))
async def cmd_list(message: types.Message):
    if not students:
        await message.answer("Пока нет ни одного студента. Добавьте через /add.")
        return
    lines = ["📋 Список студентов:"]
    for name, grades in students.items():
        avg = average(grades)
        avg_str = str(avg) if avg is not None else "нет оценок"
        lines.append(f"• {name} — средний балл: {avg_str}")
    await message.answer("\n".join(lines))

# --- Статистика по студенту ---
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /stats Имя (например: /stats Аня)")
        return
    name = parts[1].strip()
    if name not in students:
        await message.answer(f"Студент «{name}» не найден. Проверьте имя через /list.")
        return
    grades = students[name]
    if not grades:
        await message.answer(f"У студента «{name}» пока нет оценок.")
        return
    avg = average(grades)
    await message.answer(
        f"📊 Статистика: {name}\n"
        f"Оценки: {', '.join(map(str, grades))}\n"
        f"Количество оценок: {len(grades)}\n"
        f"Средний балл: {avg}\n"
        f"Лучшая оценка: {max(grades)}, худшая: {min(grades)}"
    )

# --- Топ студентов ---
@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    rated = {name: average(grades) for name, grades in students.items() if grades}
    if not rated:
        await message.answer("Пока нет студентов с оценками.")
        return
    top = sorted(rated.items(), key=lambda x: x[1], reverse=True)[:3]
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 Лучшие студенты:"]
    for i, (name, avg) in enumerate(top):
        lines.append(f"{medals[i]} {name} — {avg}")
    await message.answer("\n".join(lines))

# --- Зона риска ---
@dp.message(Command("warning"))
async def cmd_warning(message: types.Message):
    at_risk = [
        (name, average(grades))
        for name, grades in students.items()
        if grades and average(grades) < MIN_PASSING_AVG
    ]
    if not at_risk:
        await message.answer(f"Отлично! Студентов со средним баллом ниже {MIN_PASSING_AVG} нет. 🎉")
        return
    lines = [f"⚠️ Студенты в зоне риска (средний балл < {MIN_PASSING_AVG}):"]
    for name, avg in at_risk:
        lines.append(f"• {name} — {avg}")
    await message.answer("\n".join(lines))

# --- FastAPI ---
app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    update_data = await request.json()
    update = Update(**update_data)
    await dp.feed_update(bot, update)
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok", "message": "Server is running"}

@app.get("/setup")
async def setup_webhook():
    try:
        result = await bot.set_webhook(WEBHOOK_URL)
        return {"webhook": result, "url": WEBHOOK_URL}
    except Exception as e:
        return {"error": str(e)}
        
@app.get("/webhook_info")
async def webhook_info():
    try:
        info = await bot.get_webhook_info()
        return info.model_dump()
    except Exception as e:
        return {"error": str(e)}
        
@app.get("/reset_webhook")
async def reset_webhook():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        return {"status": "webhook deleted"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__maun__":
    PORT = int(os.getenv("PORT", 8080))
    print(f"🚀 Сервер запущен на порту {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
