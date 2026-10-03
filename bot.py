import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

from analyzer import analyze
from plans import get_plan
from memory import (add_analysis,get_history, clear_history)


# =========================
# Настройки
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN. Проверь файл .env")


# =========================
# Бот
# =========================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# Последние результаты
# =========================

last_results = {}


# =========================
# Клавиатуры
# =========================

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🔍 Новый анализ")
        ],
        [
            KeyboardButton(text="📚 Что умеет бот"),
            KeyboardButton(text="ℹ️ О боте")
        ]
    ],
    resize_keyboard=True
)


analysis_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🔄 Новый анализ")
        ],
        [
            KeyboardButton(text="📋 План занятий"),
            KeyboardButton(text="📚 История анализов")
        ],
        [
            KeyboardButton(text="🗑️ Очистить историю")
        ],
        [
            KeyboardButton(text="🏠 Главное меню")
        ]
    ],
    resize_keyboard=True
)
confirm_clear_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🗑️ Да, удалить"),
            KeyboardButton(text="↩️ Отмена")
        ]
    ],
    resize_keyboard=True
)
# =========================
# Состояния
# =========================

class Form(StatesGroup):
    waiting_age = State()
    waiting_description = State()


# =========================
# Главное меню
# =========================

async def show_main_menu(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )


# =========================
# /start
# =========================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await show_main_menu(message, state)


# =========================
# Новый анализ
# =========================

@dp.message(lambda message: message.text in [
    "🔍 Новый анализ",
    "🔄 Новый анализ"
])
async def new_analysis(message: Message, state: FSMContext):

    await state.clear()

    await message.answer(
        "🔍 <b>Новый анализ</b>\n\n"
        "Сколько лет ребёнку?\n\n"
        "Введите возраст числом, например: <b>5</b>",
        parse_mode="HTML"
    )

    await state.set_state(Form.waiting_age)


# =========================
# Что умеет бот
# =========================

@dp.message(lambda message: message.text == "📚 Что умеет бот")
async def bot_features(message: Message):

    await message.answer(
        "📚 <b>Что умеет бот</b>\n\n"
        "Я могу:\n"
        "▫️ анализировать описание речевых особенностей;\n"
        "▫️ находить совпадающие признаки;\n"
        "▫️ учитывать возраст ребёнка;\n"
        "▫️ показывать возможные направления работы;\n"
        "▫️ формировать примерный план занятий.\n\n"
        "⚠️ Результат является ориентировочным "
        "и не заменяет обследование специалистом.",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )


# =========================
# О боте
# =========================

@dp.message(lambda message: message.text == "ℹ️ О боте")
async def about_bot(message: Message):

    await message.answer(
        "ℹ️ <b>О боте</b>\n\n"
        "Это бот-помощник для предварительного анализа "
        "речевых особенностей ребёнка.\n\n"
        "Он сопоставляет описание пользователя "
        "с базой признаков и предлагает возможные "
        "направления коррекционной работы.\n\n"
        "Бот не устанавливает диагнозы.",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )


# =========================
# Главное меню
# =========================

@dp.message(lambda message: message.text == "🏠 Главное меню")
async def main_menu_button(message: Message, state: FSMContext):

    await show_main_menu(message, state)

    # =========================
    # Получаем возраст
    # =========================

@dp.message(Form.waiting_age)
async def process_age(message:
Message, state: FSMContext):

        try:
            age = int(message.text.strip())

            if not (0 < age < 19):
                raise ValueError

        except (ValueError, AttributeError):

            await message.answer(
                "❌ Пожалуйста, введите возраст числом от 1 до 18.\n\n"
                "Например: <b>5</b>",
                parse_mode="HTML"
            )

            return

        await state.update_data(age=age)

        await message.answer(
            "📝 <b>Теперь опишите речь и поведение ребёнка "
            "своими словами.</b>\n\n"
            "Например:\n"
            "«Не выговаривает звук Р, заменяет Л на В, "
            "быстро устаёт, отвлекается».\n\n"
            "Чем подробнее описание, тем больше признаков "
            "бот сможет сопоставить.",
            parse_mode="HTML"
        )

        await state.set_state(Form.waiting_description)

    # =========================
    # Получаем описание
    # =========================

@dp.message(Form.waiting_description)
async def process_description(
            message: Message,
            state: FSMContext
    ):

        data = await state.get_data()

        age = data.get("age", 5)
        text = message.text

        if not text:
            await message.answer(
                "Пожалуйста, напишите описание текстом."
            )

            return

        # Анализируем описание
        results = analyze(text, age=age)

        # =========================
        # Если ничего не найдено
        # =========================

        if not results:
            await message.answer(
                "🤔 <b>Подходящих признаков не найдено.</b>\n\n"
                "Попробуйте описать подробнее:\n"
                "• какие звуки ребёнок произносит неправильно;\n"
                "• понимает ли обращённую речь;\n"
                "• строит ли фразы;\n"
                "• есть ли повторения или запинки;\n"
                "• как ребёнок читает и пишет;\n"
                "• есть ли другие особенности поведения.",
                parse_mode="HTML",
                reply_markup=analysis_keyboard
            )

            await state.clear()

            return

        # =========================
        # Сохраняем последний результат
        # =========================

        user_id = message.from_user.id

        last_results[user_id] = {
            "age": age,
            "results": results
        }

        add_analysis(
            user_id,
            age,
            text,
            results
        )
        # =========================
        # Формируем результат
        # =========================

        response = (
            f"🔍 <b>Предварительный анализ</b>\n"
            f"Возраст: <b>{age} лет</b>\n\n"
        )

        for result in results:
            response += (
                f"▫️ <b>{result['name']}</b>\n"
                f"Совпадение признаков: "
                f"<b>{result['score']}%</b>\n"
                f"<i>{result['description']}</i>\n"
                f"Ключевые признаки: "
                f"{', '.join(result['matched_keywords'][:5])}\n\n"
            )

        # =========================
        # Первый найденный вариант
        # =========================

        top = results[0]

        plan = get_plan(
            top["code"],
            age
        )

        if plan:

            response += (
                f"📋 <b>Возможные направления работы</b>\n"
                f"При направлении «{top['name']}» "
                f"для возраста {age} лет:\n\n"
            )

            for number, step in enumerate(plan, 1):
                response += f"{number}. {step}\n"

        # =========================
        # Предупреждение
        # =========================

        response += (
            "\n⚠️ <b>Важно:</b>\n"
            "Результат является предварительным ориентиром "
            "по совпадению описанных признаков и не является "
            "диагнозом.\n\n"
            "Окончательное заключение и программу "
            "коррекционной работы определяет специалист "
            "после полноценного обследования ребёнка."
        )

        await message.answer(
            response,
            parse_mode="HTML",
            reply_markup=analysis_keyboard
        )

        await state.clear()

    # =========================
    # План занятий
    # =========================

@dp.message(lambda message: message.text == "📋 План занятий")
async def plan_button(message: Message):
        user_id = message.from_user.id

        saved = last_results.get(user_id)

        # Если анализа ещё не было
        if not saved:
            await message.answer(
                "📋 <b>План занятий</b>\n\n"
                "Сначала выполните анализ ребёнка "
                "через кнопку «🔄 Новый анализ».",
                parse_mode="HTML",
                reply_markup=analysis_keyboard
            )

            return

        age = saved["age"]
        results = saved["results"]

        top = results[0]

        plan = get_plan(
            top["code"],
            age
        )

        if not plan:
            await message.answer(
                "📋 Для данного направления "
                "план занятий пока не найден.",
                reply_markup=analysis_keyboard
            )

            return

        response = (
            f"📋 <b>План занятий</b>\n\n"
            f"Возраст: <b>{age} лет</b>\n"
            f"Направление: <b>{top['name']}</b>\n\n"
        )

        for number, step in enumerate(plan, 1):
            response += (
                f"<b>{number}.</b> {step}\n"
            )

        response += (
            "\n⚠️ План является ориентировочным. "
            "Конкретное содержание и длительность "
            "занятий определяет специалист после "
            "обследования ребёнка."
        )

        await message.answer(
            response,
            parse_mode="HTML",
            reply_markup=analysis_keyboard
        )
# =========================
# История анализов
# =========================

@dp.message(lambda message: message.text == "📚 История анализов")
async def history_button(message: Message):

    user_id = message.from_user.id

    history = get_history(user_id)

    if not history:
        await message.answer(
            "📚 <b>История анализов</b>\n\n"
            "У вас пока нет сохранённых анализов.",
            parse_mode="HTML",
            reply_markup=analysis_keyboard
        )
        return

    response = "📚 <b>История анализов</b>\n\n"

    for number, item in enumerate(history, 1):

        age = item["age"]
        description = item["description"]
        results = item["results"]

        date = item.get("date", "Дата неизвестна")
        time = item.get("time", "Время неизвестно")

        response += (
            f"<b>Анализ №{number}</b>\n"
            f"📅 Дата: {date}\n"
            f"🕐 Время: {time}\n"
            f"Возраст: {age} лет\n"
            f"Описание: {description}\n"
        )

        if results:
            response += (
                f"Основной результат: "
                f"{results[0]['name']} "
                f"({results[0]['score']}%)\n"
            )

        response += "\n"

    await message.answer(
        response,
        parse_mode="HTML",
        reply_markup=analysis_keyboard
    )

    # =========================
    # Очистить историю
    # =========================

@dp.message(lambda message: message.text == "🗑️ Очистить историю")
async def clear_history_button(message: Message):

        user_id = message.from_user.id

        history = get_history(user_id)

        if not history:
            await message.answer(
                "🗑️ <b>История уже пуста.</b>",
                parse_mode="HTML",
                reply_markup=analysis_keyboard
            )
            return

        await message.answer(
            "⚠️ <b>Вы действительно хотите удалить всю историю?</b>\n\n"
            "Это действие удалит все сохранённые анализы.",
            parse_mode="HTML",
            reply_markup=confirm_clear_keyboard
        )
        # =========================
        # Подтверждение очистки истории
        # =========================


@dp.message(lambda message: message.text == "🗑️ Да, удалить")
async def confirm_clear_history(message: Message):
    user_id = message.from_user.id

    clear_history(user_id)

    last_results.pop(user_id, None)

    await message.answer(
        "🗑️ <b>История анализов очищена.</b>\n\n"
        "Все сохранённые анализы удалены.",
        parse_mode="HTML",
        reply_markup=analysis_keyboard
    )


@dp.message(lambda message: message.text == "↩️ Отмена")
async def cancel_clear_history(message: Message):
    await message.answer(
        "↩️ <b>Очистка отменена.</b>\n\n"
        "История анализов сохранена.",
        parse_mode="HTML",
        reply_markup=analysis_keyboard
    )

    # =========================
    # Запуск
    # =========================

async def main():

    print("Бот запущен...")

    await dp.start_polling(bot)

print("Значение __name__:", __name__)

if __name__ == "__main__":
    print("ЗАПУСКАЮ MAIN")
    asyncio.run(main())
