# library-app

![CI](https://github.com/Soflwq/library-app/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

Модуль учёта библиотечного фонда: книги, читатели, выдача, возврат, задолженности.

## Архитектура

- **Язык:** Python 3.10+
- **GUI:** Tkinter
- **БД:** SQLite (`library.db`)
- **Структура:**
  - `main.py` — интерфейс и бизнес-логика
  - `db.py` — работа с базой данных
  - `schema.sql` — схема БД
  - `tests/` — unit-тесты (pytest)

## Запуск

```bash
pip install -r requirements.txt
python main.py
