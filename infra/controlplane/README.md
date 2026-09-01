# NOVA control plane — касса клуба

Швейцар (`awg0`) по-прежнему пускает только тех, кто в книге.
Этот сервис — касса: принимает публичный ключ телефона, выдаёт комнату `10.8.1.x` и шпаргалку с диалектом ноды.

Приватный ключ на кассу **не едет**.

## Запуск на ноутбуке

```bash
python3 infra/controlplane/server.py
```

Откройте [http://127.0.0.1:8090](http://127.0.0.1:8090).

Режим по умолчанию `NOVA_PROVISION_MODE=local`: книга пишется в SQLite, Docker не трогается. Живой тоннель тестового телефона (`10.8.1.2`) не ломается.

Журнал швейцара на ноутбуке берётся из `demo_awg_show.txt` (снимок вечера 31 августа: Amnezia и NOVA уже с `latest handshake`).

## На самой ноде (боевой режим, живой журнал)

Касса должна жить как обычная служба Linux — как nginx. Упал процесс — systemd поднимает снова. Перезагрузили VPS — касса стартует сама.

На сервере, из клона репозитория:

```bash
bash infra/scripts/10_install_controlplane.sh
```

Это кладёт файлы в `/opt/nova-controlplane`, включает `nova-controlplane.service`, открывает TCP `8090` и пишет логин/пароль дашборда в `/etc/nova-controlplane.env` (файл только на сервере, не в git).

Дашборд: `http://89.19.217.190:8090` — браузер спросит логин `nova` и пароль из того файла:

```bash
sudo cat /etc/nova-controlplane.env
```

`POST /api/v1/register` паролем дашборда не закрыт: телефон так получает комнату. Закрыты страница `/` и `GET /api/v1/overview`.

Смотреть его нужно **не** с `127.0.0.1` на Маке. Мак показывает снимок. Живые байты — только касса на ноде, которая делает `docker exec amnezia-awg2 awg show awg0`.

Если сайт с улицы России не открывается (как SSH 305), откройте ссылку **с телефона при включённой NOVA**.

`POST /api/v1/register` в этом режиме вызывает `awg set` и дописывает пир в `awg0.conf`.

## API

`POST /api/v1/register`

```json
{
  "email": "guest@example.com",
  "display_name": "Pixel",
  "public_key": "<32-byte Base64>"
}
```

Ответ — билет: endpoint, server public key, PSK, Jc/S/H/HPK/trailers, `client_address`. Без client private key.

`GET /api/v1/overview` — книга + сшивка с `awg show`.

Комнаты `10.8.1.1` (Amnezia) и `10.8.1.2` (тестовая NOVA) зарезервированы.

## Тесты

```bash
python3 -m unittest discover -s infra/controlplane/tests -v
```
