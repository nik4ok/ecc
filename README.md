# 🪐 ECC: 68 Autonomous AI Agents & Solar System Telemetry

Комплексная экосистема автономных AI-субагентов (Everything Claude Code / Cursor) с интерактивным космическим дашбордом в реальном времени и интеграцией с OpenTelemetry (Arize Phoenix).

---

## 🌟 Возможности проекта

1. **Команда из 68 субагентов по 10 отделам:**
   - 🏛 **Product & Architecture:** `planner`, `architect`, `code-architect`, `code-explorer`, `spec-miner`, `type-design-analyzer`
   - 💻 **Backend & Databases:** `database-reviewer`, `typescript-reviewer`, `python-reviewer`, `fastapi-reviewer`, `django-reviewer`, `go-reviewer`, `rust-reviewer`, `java-reviewer`, `cpp-reviewer`, `csharp-reviewer`, `fsharp-reviewer`, `php-reviewer`
   - 📱 **Frontend & Mobile UI:** `react-reviewer`, `vue-reviewer`, `flutter-reviewer`, `swift-reviewer`, `kotlin-reviewer`, `harmonyos-app-resolver`, `a11y-architect`
   - 🛠 **Build & Compilation Resolvers:** 10 узких специалистов по починке ошибок сборки
   - 🛡 **QA, Testing & Reliability:** `tdd-guide`, `e2e-runner`, `pr-test-analyzer`, `code-reviewer`, `code-simplifier`, `refactor-cleaner`, `silent-failure-hunter`, `performance-optimizer`, `comment-analyzer`
   - 🔒 **Security & Compliance:** `security-reviewer`, `healthcare-reviewer`, `opensource-sanitizer`
   - 🧠 **AI & Data Science:** `mle-reviewer`, `rag-pipeline-reviewer`, `pytorch-build-resolver`
   - 🌐 **Network & Infrastructure:** `network-architect`, `network-config-reviewer`, `network-troubleshooter`, `homelab-architect`
   - 📈 **Marketing & Growth:** `marketing-agent`, `seo-specialist`, `doc-updater`, `docs-lookup`
   - 📦 **OSS & Agent Operations:** `opensource-forker`, `opensource-packager`, `gan-planner`, `gan-generator`, `gan-evaluator`, `loop-operator`, `harness-optimizer`, `agent-evaluator`, `conversation-analyzer`, `chief-of-staff`

2. **Интерактивный дашборд «Солнечная система агентов» (`agent-solar-system.html`):**
   - 10 планетарных орбит по отделам
   - 68 спутников-агентов с неоновым свечением
   - Анимированные плазменные импульсы передачи задач между агентами
   - Инспектор агентов с превью промптов, инструментов и моделей
   - Live SSE трансляция событий в реальном времени

3. **Сервер реального времени (`solar_server.py`):**
   - Раздача дашборда на порту `8085`
   - Эндпоинт `/events` (Server-Sent Events) для мгновенной доставки импульсов
   - Эндпоинт `POST /api/trigger` для отправки сигналов от скриптов и агентов

---

## 🚀 Быстрый старт

### 1. Запуск дашборда Солнечной системы
```bash
python3 solar_server.py
```
Откройте в браузере: **`http://localhost:8085`**

### 2. Отправка импульса между агентами в реальном времени
```bash
curl -X POST http://localhost:8085/api/trigger \
  -H "Content-Type: application/json" \
  -d '{"from": "core", "to": "planner", "action": "Декомпозиция задачи"}'
```

### 3. Локальный трейсинг в Arize Phoenix
```bash
python3 -m phoenix.server.main serve
```
Откройте в браузере: **`http://localhost:6006`**

---

## 📁 Структура репозитория

```text
├── .cursor/
│   ├── agents/          # 68 файлов субагентов (ecc-*.md)
│   ├── rules/           # Правила оркестрации и воркфлоу
│   ├── skills/          # Пакетные воркфлоу и инструменты
│   └── hooks/           # Хуки жизненного цикла агентов
├── agent-solar-system.html # Интерактивная космическая карта агентов
├── solar_server.py      # HTTP + SSE сервер телеметрии
└── README.md
```
