# GEDS — слой данных и пайплайн (рус.)

Краткое руководство по работе с CSV-слоем и научным пайплайном GEDS.

## Структура файлов

```
backend/data/csv/
├── historical_events.csv      ← 12 событий (8 в графе + 4 для расширения)
├── model_parameters.csv       ← 14 параметров с диапазонами и литературой
└── validation_datasets.csv    ← 14 источников данных + лимиты и лицензии

backend/app/data/
└── csv_loader.py              ← Парсер CSV → типизированные dataclasses

backend/app/core/                ← научный пайплайн (уже реализован)
├── mcmc.py                    /api/v1/posterior          (Bayesian inference)
├── de_calibrate.py            scripts/_smoke2.py         (DE-калибровка)
├── postcalibration.py         /api/v1/calibration-report (изотонная пост-калибровка)
├── cross_validation.py        /api/v1/cv-report          (LOO-CV)
├── benchmark.py               /api/v1/benchmark          (лидерборд моделей)
├── ablation.py                /api/v1/ablation           (покомпонентная аблация)
├── sensitivity.py             scripts/_smoke3.py         (Sobol-чувствительность)
├── tail_risk.py               /api/v1/tail-risk          (VaR/CVaR/fan-chart)
├── research_metrics.py        /api/v1/research-metrics   (SFI/RES/CCS/ERT/SAC)
└── baselines.py               (Leontief + linear diffusion)

docs/
├── CLAUDE_PROMPT.ru.md        ← Системный промпт для ассистента
├── README.ru.md               ← Этот файл
└── AUDIT.md                   ← Научный аудит (английский)
```

## Быстрый старт

### Шаг 1. Проверьте, что CSV корректно загружаются

```cmd
cd /d D:\GEDS\backend
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" ^
    -c "from app.data.csv_loader import load_historical_events_csv, load_parameters_csv, load_datasets_csv; ^
        e = load_historical_events_csv(); ^
        p = load_parameters_csv(); ^
        d = load_datasets_csv(); ^
        print(f'events: {len(e)} (in_graph={sum(1 for x in e if x.in_geds_graph)})'); ^
        print(f'params: {len(p)}'); ^
        print(f'datasets: {len(d)}')"
```

Ожидаемый вывод:

```
events: 12 (in_graph=8)
params: 14
datasets: 14
```

### Шаг 2. Запустите полный пайплайн (~5 минут)

```cmd
cd /d D:\GEDS\backend
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" scripts/_smoke.py
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" scripts/_smoke2.py
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" scripts/_smoke3.py
```

Это запустит:

1. **MCMC** — апостериорные распределения параметров
2. **LOO-CV** — out-of-sample кросс-валидация
3. **Baselines** — сравнение SEIRS vs Leontief vs Diffusion vs naive
4. **Novel metrics** — SFI/RES/CCS/ERT/SAC + permutation tests
5. **Isotonic post-calibration** — out-of-sample оценка
6. **DE-калибровка** — multi-restart spread
7. **Tail-risk** — VaR/CVaR/fan-chart
8. **Sobol** — глобальная чувствительность
9. **Benchmark** — лидерборд моделей с Murphy skill score
10. **Ablation** — покомпонентная важность

Все результаты сохраняются в `backend/data/calibration/*.json`.

### Шаг 3. Запустите backend и frontend

```cmd
cd /d D:\GEDS\backend
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" -m uvicorn app.main:app --reload
```

В другом окне:

```cmd
cd /d D:\GEDS\frontend
npm run dev
```

Откройте:

- `http://localhost:3000`            — главный dashboard
- `http://localhost:3000/validation` — все валидационные панели (live)

## Конвейер задач

Полный пайплайн вызывает эти эндпоинты в порядке:

```
1. GET  /api/v1/data/historical-events-csv   ← CSV-источник истины
2. POST /api/v1/simulate                     ← одна симуляция
3. POST /api/v1/monte-carlo                  ← неопределённость
4. POST /api/v1/tail-risk                    ← VaR/CVaR на хвостах
5. GET  /api/v1/cv-report                    ← out-of-sample skill
6. GET  /api/v1/posterior                    ← MCMC параметры (если запущен)
7. GET  /api/v1/calibration-report           ← изотонная пост-калибровка
8. GET  /api/v1/ablation                     ← компонентная важность
9. GET  /api/v1/benchmark                    ← лидерборд моделей
10. GET /api/v1/research-metrics             ← SFI/RES/CCS/ERT/SAC + p-values
```

## Выходные файлы

| Файл | Содержимое |
|---|---|
| `data/calibration/posterior.json` | MCMC mean/std/p05/p95/sens по параметру |
| `data/calibration/cv_report.json` | LOO-CV с bootstrap-CI |
| `data/calibration/benchmark.json` | Лидерборд SEIRS/Leontief/Diffusion/Naive |
| `data/calibration/ablation.json` | Покомпонентная важность с Δ MAE/Pearson |
| `data/calibration/sobol.json` | Sobol S1/ST + рейтинг параметров |
| `data/calibration/isotonic.json` | Сериализованная пост-калибровка |
| `data/calibration/de_result.json` | DE multi-restart spread |

## Внешние ресурсы (что нужно от пользователя)

| Ресурс | Тип | Кто предоставляет |
|---|---|---|
| UN Comtrade API-ключ | необходим для расширения графа | **Пользователь** (https://comtrade.un.org/api) |
| OECD ICIO/STAN/TiVA bulk download | необходим для расширения графа | **Пользователь** (через сайт OECD) |
| 30-50 размеченных событий | необходим для статистической мощности | **Совместная литературная работа** (~60 часов) |
| GPU для GNN-замены D_eff | опционально, не блокирует | **Пользователь** (если будет нужно) |
| Платная подписка Lloyd's Route Risk | опционально | **Пользователь** (на текущей стадии необязательно) |

## Ограничения текущего CSV

`historical_events.csv` содержит 12 событий, но только 8 (`in_geds_graph=yes`)
можно прогонять через бэктест. Остальные 4 сохранены для будущей валидации
после расширения графа:

- **9/11 (2001)** — нет авиационного сектора в графе
- **SARS (2003)** — нет сервисного сектора в графе
- **Финкризис (2008)** — финансовый шок, GEDS моделирует торговые потоки
- **РФ-Украина (2022)** — нет RUS/UKR узлов в графе

После того как граф расширится до 80+ узлов с авиа/сервис/энергия секторами
и RUS/UKR/BRA/IDN странами, все 12 событий станут backtest-применимыми
без изменений в коде — достаточно поменять `in_geds_graph=yes` в CSV.

## Что говорить судьям ISEF (краткий honest summary)

> "Мы построили рамку (framework) которая позволяет любому загрузить CSV
> с историческими событиями и параметрами и получить out-of-sample skill
> score, posterior distribution для каждого параметра, sensitivity analysis,
> ablation study, и сравнение с baseline-моделями. Текущая выборка (N=8
> событий в графе) недостаточна для значимых выводов — Murphy skill score
> нашей сложной модели сравним с naive baseline. Линейная диффузия
> побеждает на текущих данных. Это означает, что архитектура движка
> правильная, но данных мало. План расширения: N≥30 событий + граф
> 200+ узлов из UN Comtrade. Эта диагностика — основной результат нашей
> работы."

Этот тип ответа судьи ISEF ценят выше, чем "наша модель показывает r=+0.97".
