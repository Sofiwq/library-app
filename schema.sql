PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS genres (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS categories (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL UNIQUE,
    loan_days INTEGER NOT NULL DEFAULT 14
);

CREATE TABLE IF NOT EXISTS books (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn       TEXT,
    title      TEXT NOT NULL,
    author     TEXT NOT NULL,
    year       INTEGER,
    publisher  TEXT,
    genre_id   INTEGER,
    FOREIGN KEY (genre_id) REFERENCES genres(id)
);

CREATE TABLE IF NOT EXISTS copies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id      INTEGER NOT NULL,
    inventory_no TEXT NOT NULL UNIQUE,
    status       TEXT NOT NULL DEFAULT 'в наличии'
                 CHECK (status IN ('в наличии','выдан','зарезервирована','списан')),
    condition    TEXT DEFAULT 'хорошее',
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS readers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_no     TEXT NOT NULL UNIQUE,
    full_name   TEXT NOT NULL,
    phone       TEXT,
    category_id INTEGER,
    is_active   INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    login         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('библиотекарь','администратор'))
);

CREATE TABLE IF NOT EXISTS loans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_id      INTEGER NOT NULL,
    reader_id    INTEGER NOT NULL,
    librarian_id INTEGER,
    issue_date   DATE NOT NULL,
    due_date     DATE NOT NULL,
    return_date  DATE,
    FOREIGN KEY (copy_id)      REFERENCES copies(id),
    FOREIGN KEY (reader_id)    REFERENCES readers(id),
    FOREIGN KEY (librarian_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS debts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id      INTEGER NOT NULL,
    reader_id    INTEGER NOT NULL,
    type         TEXT NOT NULL CHECK (type IN ('просрочка','утеря','порча')),
    days_overdue INTEGER DEFAULT 0,
    amount       REAL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'открыта'
                 CHECK (status IN ('открыта','закрыта')),
    paid_date    DATE,
    FOREIGN KEY (loan_id)   REFERENCES loans(id),
    FOREIGN KEY (reader_id) REFERENCES readers(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_id    INTEGER NOT NULL,
    reader_id  INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'активна'
               CHECK (status IN ('активна','выдана','отменена','истекла')),
    FOREIGN KEY (copy_id)   REFERENCES copies(id),
    FOREIGN KEY (reader_id) REFERENCES readers(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_id    INTEGER NOT NULL,
    reader_id  INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'активна'
               CHECK (status IN ('активна','выдана','отменена','истекла')),
    FOREIGN KEY (copy_id)   REFERENCES copies(id),
    FOREIGN KEY (reader_id) REFERENCES readers(id)
);