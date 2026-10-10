import json
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
            text = message.get("text", "")
            chat_id = chat.get("id")

            if not chat_id:
                return Response("OK", status=200)

            if text == "/start":
                answer = (
                    "Привет! 👋\n\n"
                    "Я помощник логопеда-дефектолога.\n"
                    "Помогаю разбирать описания речевых трудностей "
                    "и подбирать направления работы.\n\n"
                    "Напиши /help, чтобы узнать больше."
                )

            elif text == "/help":
                answer = (
                    "📚 Я умею анализировать описания речевых трудностей.\n\n"
                    "Отправь описание и возраст ребёнка.\n"
                    "Например: Ребёнок 5 лет не выговаривает звук Р."
                )

            elif text == "/plan":
                answer = (
                    "📋 Чтобы подобрать план занятий, сначала отправь "
                    "описание речевых трудностей ребёнка и его возраст."
                )

            else:
                results = analyze(text)

            if results:
                result = results[0]

                age = None
                words = text.split()

                for word in words:
                    clean_word = word.strip(".,!?;:")
                    if clean_word.isdigit():
                        number = int(clean_word)
                        if 1 <= number <= 18:
                            age = number
                            break

                if age is not None:
                    await self.env.HISTORY.put(
                        str(chat_id),
                        json.dumps({
                            "age": age,
                            "code": result.get("code"),
                            "name": result.get("name")
                                                }, ensure_ascii=False)
                                            )
                    answer = (
                        "🔍 Предварительный результат анализа\n\n"
                        f"Возможный вариант: {result.get('name', 'Не определён')}\n"
                        f"Совпадение: {result.get('score', 0)}%\n\n"
                        f"{result.get('description', '')}\n\n"
                        "⚠️ Это ориентировочная оценка, а не диагноз. "
                        "Для уточнения обратитесь к логопеду-дефектологу."
                    )
                else:
                    answer = (
                        "Пока не удалось найти достаточно совпадений.\n\n"
                        "Опиши подробнее, какие именно речевые "
                        "трудности наблюдаются и в каком возрасте."
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
            return Response("Error", status=500)
