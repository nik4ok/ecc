# NOVA Telegram-бот — витрина

Бот — магазин: оплата, файл APK, статус подписки. VPN по-прежнему включает приложение на телефоне.

## Что умеет

- `/start` — как поставить NOVA без Google Play
- **Оплатить** — счёт в Telegram Stars на 30 дней
- **Скачать NOVA** — файл APK, только после оплаты
- **Мой статус** — до какой даты доступ

Mini App нет. Касса `8090` пока не связана: пир по-прежнему выдаёт приложение при первом запуске.

## Локально (без живого Telegram)

```bash
python3 -m unittest discover -s infra/bot/tests -v
```

Режим `NOVA_PAYMENTS=dev` зачисляет 30 дней без Stars — только локально и только вместе с `NOVA_DEV_PAY=1`. На сервер это не ставьте.

## Боевой запуск на ноде

1. В [@BotFather](https://t.me/BotFather) создайте бота, скопируйте токен. В настройках бота выключите группы (Allow Groups → Off).
2. На VPS:

```bash
bash infra/scripts/11_install_bot.sh
```

3. Впишите токен (файл только на сервере, не в git):

```bash
sudo nano /etc/nova-bot.env
# NOVA_BOT_TOKEN=123456:ABC...
# NOVA_PAYMENTS=stars
# NOVA_STARS_PRICE=250
sudo systemctl start nova-bot
```

4. Положите сборку:

```bash
sudo cp nova-release.apk /var/lib/nova-bot/NOVA.apk
```

Цена в Stars задаётся `NOVA_STARS_PRICE`. 250 — стартовое значение, его можно сменить без пересборки бота.

## Проверка

```bash
journalctl -u nova-bot -f
```

Напишите боту `/start`, нажмите «Оплатить». После успешного платежа должен прийти `NOVA.apk`.
