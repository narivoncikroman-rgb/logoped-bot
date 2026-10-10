import json

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
                    "📚 Что я умею:\n"
                    "• Помогать анализировать описание речевых трудностей.\n"
                    "• Подбирать направления работы.\n"
                    "• Помогать составлять планы занятий.\n\n"
                    "Важно: мои ответы не заменяют консультацию специалиста."
                )
            else:
                answer = (
                    "Я получил твоё сообщение! 👍\n\n"
                    "Сейчас подключаем мои функции. "
                    "Скоро здесь появится анализ речевых трудностей."
                )

            token = self.env.BOT_TOKEN
            url = f"https://api.telegram.org/bot{token}/sendMessage"

            await fetch(
                url,
                {
                    "method": "POST",
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "body": json.dumps({
                        "chat_id": chat_id,
                        "text": answer
                    })
                }
            )

            return Response("OK", status=200)

        except Exception as error:
            print(f"Webhook error: {error}")
            return Response("Error", status=500)
