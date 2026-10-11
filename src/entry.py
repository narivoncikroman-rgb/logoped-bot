import json
from datetime import datetime, timezone

from analyzer import analyze
from plans import get_plan
from workers import WorkerEntrypoint, Response, fetch


MAIN_KEYBOARD = {
    "keyboard": [
        [
            {"text": "🔍 Новый анализ"},
            {"text": "📋 План занятий"}
        ],
        [
            {"text": "📚 История анализов"},
            {"text": "🗑️ Очистить историю"}
        ],
        [
            {"text": "ℹ️ О боте"}
        ]
    ],
    "resize_keyboard": True
}

CONFIRM_KEYBOARD = {
    "keyboard": [
        [
            {"text": "🗑️ Да, удалить"},
            {"text": "↩️ Отмена"}
        ]
    ],
    "resize_keyboard": True
}


class Default(WorkerEntrypoint):

    async def fetch(self, request):
        if request.method != "POST":
            return Response(
                "Logoped bot worker is running!",
                status=200
            )

        try:
            update = await request.json()
            message = update.get("message", {})
            chat = message.get("chat", {})
            text = message.get("text", "").strip()
            chat_id = chat.get("id")

            if not chat_id or not text:
                return Response("OK", status=200)

            user_key = str(chat_id)
            history_key = f"history:{user_key}"
            confirm_key = f"clear_confirm:{user_key}"

            answer = ""
            keyboard = MAIN_KEYBOARD

            pending = await self.env.HISTORY.get(confirm_key)

            if pending and text not in (
                "🗑️ Да, удалить",
                "↩️ Отмена"
            ):
                await self.env.HISTORY.delete(confirm_key)
                pending = None

            # Подтверждение удаления истории
            if text == "🗑️ Да, удалить" and pending:
                await self.env.HISTORY.delete(history_key)
                await self.env.HISTORY.delete(user_key)
                await self.env.HISTORY.delete(confirm_key)

                answer = "✅ История анализов очищена."

            elif text == "↩️ Отмена" and pending:
                await self.env.HISTORY.delete(confirm_key)
                answer = "Удаление отменено. История сохранена."

            # Главное меню
            elif text in ("/start", "🏠 Главное меню"):
                answer = (
                    "Привет! 👋\n\n"
                    "Я помощник логопеда-дефектолога.\n"
                    "Выбери действие в меню ниже.\n\n"
                    "🔍 Новый анализ — анализ речевых трудностей\n"
                    "📋 План занятий — план по последнему анализу\n"
                    "📚 История анализов — прошлые результаты\n"
                    "🗑️ Очистить историю — удалить записи\n"
                    "ℹ️ О боте — информация о помощнике"
                )

            # Информация о боте
            elif text in ("/help", "ℹ️ О боте"):
                answer = (
                    "ℹ️ О боте\n\n"
                    "Я помогаю предварительно анализировать "
                    "описания речевых трудностей и подбирать "
                    "направления работы.\n\n"
                    "Отправь описание и возраст ребёнка.\n"
                    "Например: Ребёнок 5 лет не выговаривает звук Р.\n\n"
                    "Результат не является диагнозом. "
                    "Для оценки ребёнка обратись к "
                    "логопеду-дефектологу."
                )

            # Начало нового анализа
            elif text in ("/new", "🔍 Новый анализ"):
                answer = (
                    "🔍 Напиши описание речевых трудностей "
                    "и возраст ребёнка.\n\n"
                    "Например: Ребёнок 5 лет не выговаривает звук Р."
                )

            # Просмотр истории
            elif text in ("/history", "📚 История анализов"):
                saved_history = await self.env.HISTORY.get(
                    history_key
                )
                if not saved_history:
                    answer = (
                        "📚 История пока пуста.\n\n"
                        "Отправь описание речевых трудностей, "
                        "чтобы сохранить первый анализ."
                    )
                else:
                    history = json.loads(saved_history)
                    lines = ["📚 Последние анализы:\n"]

                    for i, item in enumerate(
                        reversed(history), 1
                    ):
                        age = item.get("age")
                        age_text = (
                            f"{age} лет"
                            if age is not None
                            else "возраст не указан"
                        )

                        lines.append(
                            f"{i}. {item.get('date', '')}\n"
                            f"Возраст: {age_text}\n"
                            f"Описание: {item.get('description', '')}\n"
                            f"Результат: {item.get('name', 'Не определён')}\n"
                            f"Совпадение: {item.get('score', 0)}%\n"
                        )

                    answer = "\n".join(lines)

            # План занятий по последнему анализу
            elif text in ("/plan", "📋 План занятий"):
                saved = await self.env.HISTORY.get(user_key)

                if not saved:
                    answer = (
                        "📋 Сначала отправь описание речевых "
                        "трудностей и возраст ребёнка."
                    )
                else:
                    data = json.loads(saved)
                    age = data.get("age")
                    code = data.get("code")
                    description = data.get("description", "")

                    if age is None:
                        answer = (
                            "Не удалось определить возраст.\n\n"
                            "Отправь описание с возрастом цифрами, "
                            "например: Ребёнку 5 лет трудно "
                            "произносить звук Р."
                        )
                    else:
                        plan = (
                            get_plan(code, age, description)
                            if code
                            else None
                        )

                        if plan:
                            answer = (
                                "📋 План занятий\n"
                                f"Возраст: {age} лет\n"
                                f"Направление: "
                                f"{data.get('name', 'Не определено')}\n\n"
                                + "\n".join(
                                    f"{i}. {item}"
                                    for i, item in enumerate(plan, 1)
                                )
                                + "\n\n⚠️ План ориентировочный. "
                                "Учитывай рекомендации специалиста."
                            )
                        else:
                            answer = (
                                "Не удалось подобрать план для "
                                "этого результата. Попробуй отправить "
                                "новое описание речевых трудностей."
                            )

            # Очистка истории
            elif text in ("/clear", "🗑️ Очистить историю"):
                await self.env.HISTORY.put(confirm_key, "1")

                answer = (
                    "⚠️ Ты действительно хочешь удалить историю "
                    "анализов и последний сохранённый результат?\n\n"
                    "Это действие нельзя отменить."
                )

                keyboard = CONFIRM_KEYBOARD

            # Анализ обычного текстового сообщения
            else:
                age = None
                for word in text.split():
                    clean_word = word.strip(".,!?;:()")
                    if clean_word.isdigit():
                        number = int(clean_word)
                        if 1 <= number <= 18:
                            age = number
                            break

                results = analyze(text, age=age)

                if results:
                    result = results[0]

                    # Сохраняем запись в истории
                    entry = {
                        "date": datetime.now(
                            timezone.utc
                        ).strftime("%d.%m.%Y %H:%M UTC"),
                        "description": text,
                        "age": age,
                        "code": result.get("code"),
                        "name": result.get("name"),
                        "score": result.get("score", 0)
                    }

                    saved_history = await self.env.HISTORY.get(
                        history_key
                    )

                    history = (
                        json.loads(saved_history)
                        if saved_history
                        else []
                    )

                    history.append(entry)
                    history = history[-20:]

                    await self.env.HISTORY.put(
                        history_key,
                        json.dumps(
                            history,
                            ensure_ascii=False
                        )
                    )

                    # Сохраняем последний результат для плана
                    await self.env.HISTORY.put(
                        user_key,
                        json.dumps({
                            "age": age,
                            "code": result.get("code"),
                            "name": result.get("name"),
                            "description": text
                        }, ensure_ascii=False)
                    )

                    # Формируем ответ со всеми найденными вариантами
                    sections = [
                        "🔍 Предварительный результат анализа\n"
                    ]

                    for i, item in enumerate(results, 1):
                        sections.append(
                            f"{i}. {item.get('name', 'Не определён')}\n"
                            f"Совпадение: {item.get('score', 0)}%\n"
                            f"{item.get('description', '')}"
                        )

                        matched = item.get("matched_keywords", [])

                        if matched:
                            sections.append(
                                "Найденные признаки: "
                                + ", ".join(matched[:5])
                            )

                    # Добавляем план к основному результату,
                    # только если возраст удалось определить
                    if age is not None:
                        plan = get_plan(
                            result.get("code"),
                            age,
                            text
                        )

                        if plan:
                            sections.append(
                                "📋 Примерный план занятий:\n"
                                + "\n".join(
                                    f"{i}. {item}"
                                    for i, item in enumerate(plan, 1)
                                )
                            )

                    sections.append(
                        "✅ Анализ сохранён в истории."
                    )

                    sections.append(
                        "⚠️ Это ориентировочная оценка, а не диагноз. "
                        "План необходимо адаптировать к ребёнку "
                        "вместе с логопедом-дефектологом."
                    )

                    answer = "\n\n".join(sections)
                    else:
                    answer = (
                        "Пока не удалось найти достаточно совпадений.\n\n"
                        "Опиши подробнее речевые трудности "
                        "и укажи возраст ребёнка цифрами."
                    )

            # Отправляем ответ в Telegram
            token = self.env.BOT_TOKEN
            url = (
                f"https://api.telegram.org/bot{token}/sendMessage"
            )

            await fetch(
                url,
                method="POST",
                headers={
                    "Content-Type": "application/json"
                },
                body=json.dumps({
                    "chat_id": chat_id,
                    "text": answer,
                    "reply_markup": keyboard
                }, ensure_ascii=False)
            )

            return Response("OK", status=200)

        except Exception as error:
            print(f"Webhook error: {error}")
            return Response(
                "Internal Server Error",
                status=500
            )
