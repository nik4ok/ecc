# NOVA control plane — касса

Швейцар на двери (`awg0`) пускает только тех, кто в книге.
Этот сервис — касса в **офисе**: принимает публичный ключ телефона, выдаёт комнату `10.8.1.x` и шпаргалку с диалектом ноды. На дверь касса говорит «вписать пир» по SSH.

Приватный ключ на кассу **не едет**.

## Запуск на ноутбуке

```bash
python3 infra/controlplane/server.py
```

Откройте [http://127.0.0.1:8090](http://127.0.0.1:8090).

Режим по умолчанию `NOVA_PROVISION_MODE=local`: книга пишется в SQLite, дверь не трогается. Журнал швейцара берётся из `demo_awg_show.txt`.

## На офисе (боевой режим)

Касса живёт как служба Linux. Docker на офисе не нужен.

```bash
bash infra/scripts/10_install_controlplane.sh
```

Скрипт кладёт файлы в `/opt/nova-controlplane`, пишет логин/пароль дашборда в `/etc/nova-controlplane.env` и ставит `NOVA_PROVISION_MODE=ssh`.

Ключ на дверь (один раз):

```bash
ssh-keygen -t ed25519 -f /etc/nova-controlplane/edge_ed25519 -N ""
ssh-copy-id -i /etc/nova-controlplane/edge_ed25519.pub root@89.19.217.190
systemctl start nova-controlplane
```

Дашборд: `http://72.56.118.39:8090` — логин `nova`, пароль из того файла:

```bash
sudo cat /etc/nova-controlplane.env
```

`POST /api/v1/register` паролем не закрыт: телефон так получает комнату. Закрыты страница `/` и `GET /api/v1/overview`.

В дашборде карточки дверей: IP, активна / неактивна, сколько пиров.

Если кассу ставят **на самой двери** и крутится `amnezia-awg2`, установщик сам выберет `NOVA_PROVISION_MODE=docker`.

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

`GET /api/v1/overview` — книга, сшивка с `awg show`, список нод (`nodes`: IP, status, peer_count).

Комнаты `10.8.1.1` (Amnezia) и `10.8.1.2` (тестовая NOVA) зарезервированы.

## Тесты

```bash
python3 -m unittest discover -s infra/controlplane/tests -v
```
