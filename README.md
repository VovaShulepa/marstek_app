# Marstek Venus E — Local Monitoring & Control (PWA)

Локальна Progressive Web App для моніторингу та керування станцією **Marstek Venus E (5.12 кВт·год)** через **UDP JSON-RPC Open API** (порт `30000`).

UI: гібрид EcoFlow (hero SOC + animated energy flow) × Marstek (dark modular cards). Усі підписи українською.

## Можливості

- Live телеметрія через WebSocket кожні ~2 с
- Розрахунок «часу до розряду / заряду» з rolling average потужності
- Режими: Auto / AI / Manual / Passive + ліміти потужності
- DEMO-симулятор без фізичної станції
- PWA: встановлення на iPhone / Android як standalone-додаток
- Відкриття з ноутбука в браузері в локальній мережі

## Структура

```
backend/     FastAPI + UDP client + simulator + /ws
frontend/    React + Vite + Tailwind + Framer Motion + PWA
docker-compose.yml
```

## Швидкий старт (DEMO)

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# DEMO_MODE=true за замовчуванням
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Відкрий: **http://localhost:5173**

З іншого пристрою в тій же Wi‑Fi мережі: `http://<IP-ноутбука>:5173`

## Підключення до реальної станції

1. Переконайся, що телефон/ноут і Venus E в одній LAN.
2. Дізнайся IP станції (роутер / Marstek app).
3. У backend `.env`:

```env
DEMO_MODE=false
MARSTEK_IP=192.168.x.x
MARSTEK_PORT=30000
MIN_SOC_RESERVE_PCT=10
INVERTER_EFFICIENCY=0.95
```

4. Або через шестерню в UI → IP / порт / резерв SOC / ККД / вимкнути DEMO.

UDP методи: `Bat.GetStatus`, `ES.GetStatus`, `ES.SetMode` / `ES.SetPower`.

## Docker

```bash
DEMO_MODE=true docker compose up --build
```

- UI: http://localhost:5173  
- API: http://localhost:8000  

На Linux для UDP у локальну мережу може знадобитись `network_mode: host` для backend.

## PWA на телефоні

1. Відкрий UI у Safari (iOS) або Chrome (Android) по `http://<IP-ПК>:5173`
2. **Додати на екран «Домашній» / Install app**
3. Запускається fullscreen без адресного рядка

> Для installability iOS іноді потребує HTTPS. У домашній мережі можна використати reverse proxy з TLS або тунель; для LAN-тесту HTTP часто достатньо «Add to Home Screen».

## API

| Метод | Шлях | Опис |
|-------|------|------|
| GET | `/api/health` | Статус |
| GET | `/api/state` | Поточний стан |
| POST | `/api/mode` | `{ "mode": "Auto", "power_limit_w": 1500 }` |
| POST | `/api/config` | IP, резерв SOC, efficiency, demo |
| POST | `/api/simulator` | Override навантаження / SOC / Вт |
| WS | `/ws` | Live JSON state |

## Примітки

- Час залишку рахується від енергії **вище** `MIN_SOC_RESERVE_PCT` (заводські 12% від 5120 Wh).
- Середня потужність — вікно ~120 с, щоб короткі стрибки (компресор холодильника) не «стрибали» ETA.
