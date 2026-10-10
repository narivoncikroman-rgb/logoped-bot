import json
from datetime import datetime, timezone

from analyzer import analyze
from plans import get_plan
from workers import WorkerEntrypoint, Response, fetch


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

            if not chat_id:
                return Response("OK", status=200)

            user_key = str(chat_id)
            history_key = f"history:{user_key}"

            if text == "/start":
                answer = (
                    "Привет! 👋\n\n"
                    "Я помощник логопеда-дефектолога.\n"
                    "Помогаю разбирать описания речевых трудностей "
                    "и подбирать направления работы.\n\n"
                    "Команды:\n"
                    "/help — помощь\n"
                    "/plan — план занятий\n"
                    "/history — история анализов"
                )

            elif text == "/help":
                answer = (
                    "📚 Я умею анализировать описания речевых трудностей.\n\n"
                    "Отправь описание и возраст ребёнка.\n"
                    "Например: Ребёнок 5 лет не выговаривает звук Р.\n\n"
                    "/plan — план занятий\n"
                    "/history — история анализов"
                )

            elif text == "/history":
                saved_history = await self.env.HISTORY.get(history_key)

                if not saved_history:
                    answer = (
                        "📚 История пока пуста.\n\n"
                        "Отправь описание речевых трудностей, "
                        "чтобы сохранить первый анализ."
                    )
                else:
                    history = json.loads(saved_history)

                    lines = ["📚 Последние анализы:\n"]

                    for i, item in enumerate(reversed(history), 1):
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

            elif text == "/plan":
                saved = await self.env.HISTORY.get(user_key)

                if not saved:
                    answer = (
                        "📋 Сначала отправь описание речевых трудностей "
                        "и возраст ребёнка.\n\n"
                        "Например: Ребёнок 5 лет не выговаривает звук Р."
                    )
                else:
                    data = json.loads(saved)
                    age = data.get("age")
                    code = data.get("code")

                    plan = get_plan(code, age) if code and age else None

                    if plan:
                        answer = (
                            f"📋 План занятий\n"
                            f"Возраст: {age} лет\n"
                            f"Направление: {data.get('name', 'Не определено')}\n\n"
                            + "\n".join(
                                f"{i}. {item}"
                                for i, item in enumerate(plan, 1)
                            )
                            + "\n\n⚠️ План ориентировочный. "
                            "Упражнения следует подбирать с учётом "
                            "рекомендаций специалиста."
                        )
                    else:
                        answer = (
                            "Не удалось подобрать план для этого результата. "
                            "Попробуй отправить описание ещё раз."
                        )

            else:
                results = analyze(text)

                if results:
                    result = results[0]
                    age = None

                    for word in text.split():
                        clean_word = word.strip(".,!?;:")
                        if clean_word.isdigit():
                            number = int(clean_word)
                            if 1 <= number <= 18:
                                age = number
                                break

                    entry = {
                        "date": datetime.now(timezone.utc).strftime(
                            "%d.%m.%Y %H:%M UTC"
                        ),
                        "description": text,
                        "age": age,
                        "code": result.get("code"),
                        "name": result.get("name"),
                        "score": result.get("score", 0)
                    }

                    saved_history = await self.env.HISTORY.get(history_key)

                    if saved_history:
                        history = json.loads(saved_history)
                    else:
                        history = []

                    history.append(entry)
                    history = history[-20:]

                    await self.env.HISTORY.put(
                        history_key,
                        json.dumps(history, ensure_ascii=False)
                    )

                    if age is not None:
                        await self.env.HISTORY.put(
                            user_key,
                            json.dumps({
                                "age": age,
                                "code": result.get("code"),
                                "name": result.get("name")
                            }, ensure_ascii=False)
                        )

                    answer = (
                        "🔍 Предварительный результат анализа\n\n"
                        f"Возможный вариант: "
                        f"{result.get('name', 'Не определён')}\n"
                        f"Совпадение: {result.get('score', 0)}%\n\n"
                        f"{result.get('description', '')}\n\n"
                        "✅ Анализ сохранён в истории.\n\n"
                        "⚠️ Это ориентировочная оценка, а не диагноз. "
                        "Для уточнения обратитесь к логопеду-дефектологу."
                    )
                else:
                    answer = (
                        "Пока не удалось найти достаточно совпадений.\n\n"
                        "Опиши подробнее, какие речевые трудности "
                        "наблюдаются и в каком возрасте."
                    )

            token = self.env.BOT_TOKEN
            url = f"https://api.telegram.org/bot{token}/sendMessage"

            await fetch(
                url,
                method="POST",
                headers={
                    "Content-Type": "application/json"
                },
                body=json.dumps({
                    "chat_id": chat_id,
                    "text": answer
                })
            )

            return Response("OK", status=200)

        except Exception as error:
            print(f"Webhook error: {error}")
            return Response("Internal Server Error", status=500)
