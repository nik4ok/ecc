# NOVA Telegram-бот — витрина

Бот — вход: приветствие, выбор телефона, превью APK для Android. VPN включает приложение на телефоне, не чат.

Оплата сейчас **закрыта** (`NOVA_PAYMENTS=off`). iPhone честно ждёт: кнопки на месте, файла и кассы нет.

## Путь человека

1. `/start` — обращение по имени, вопрос «с какого телефона».
2. **Android** — можно скачать превью и поставить, как Amnezia.
3. **iPhone** — нет App Store и TestFlight; «Скачать» и «Оплатить» ничего не делают.
4. **Оплатить** — объясняет, что касса ещё не подключена. Счёта нет.
5. **Мой статус** — подписки нет, списывать нечего.
6. **Сообщить о проблеме** — следующим сообщением опишите сбой; бот сохранит его. Пароли и ключи не присылать.

Когда касса появится, на сервере поставьте `NOVA_PAYMENTS=stars`.

## Локально

```bash
python3 -m unittest discover -s infra/bot/tests -v
```

`NOVA_PAYMENTS=dev` вместе с `NOVA_DEV_PAY=1` — только локальная проверка, не на сервер.

## Боевой запуск на ноде

1. В [@BotFather](https://t.me/BotFather) создайте бота, скопируйте токен. Выключите группы.
2. На VPS:

```bash
bash infra/scripts/11_install_bot.sh
```

3. Токен только на сервере:

```bash
sudo nano /etc/nova-bot.env
# NOVA_BOT_TOKEN=123456:ABC...
# NOVA_PAYMENTS=off
sudo systemctl start nova-bot
```

4. Android-сборка:

```bash
sudo cp nova-release.apk /var/lib/nova-bot/NOVA.apk
```

## Проверка

```bash
journalctl -u nova-bot -f
```

Напишите боту `/start`, выберите Android, нажмите «Скачать NOVA».
