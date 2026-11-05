import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import date, timedelta, datetime
import csv

from db import get_connection, init_db, check_login, get_setting

APP_TITLE = "БиблиоУчет — модуль учета библиотечного фонда"

# ============== ЛОГИКА ШТРАФОВ ==============
def calc_fine(days_overdue):
    per_day = float(get_setting("fine_per_day", "10"))
    max_fine = float(get_setting("fine_max", "500"))
    return min(days_overdue * per_day, max_fine)

def has_open_debt(reader_id):
    conn = get_connection()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM debts WHERE reader_id=? AND status='открыта'",
        (reader_id,)).fetchone()[0]
    conn.close()
    return cnt > 0

# ============== РЕЗЕРВЫ ==============
def expire_reservations():
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT id, copy_id FROM reservations WHERE status='активна' AND expires_at < ?",
        (now,)).fetchall()
    for r in rows:
        conn.execute("UPDATE reservations SET status='истекла' WHERE id=?", (r["id"],))
        conn.execute("UPDATE copies SET status='в наличии' WHERE id=? AND status='зарезервирована'",
                     (r["copy_id"],))
    conn.commit()
    conn.close()

def create_reservation(copy_id, reader_id):
    days = int(get_setting("reserve_days", "3"))
    now = datetime.now()
    exp = now + timedelta(days=days)
    conn = get_connection()
    conn.execute(
        "INSERT INTO reservations(copy_id, reader_id, created_at, expires_at) VALUES (?,?,?,?)",
        (copy_id, reader_id, now.isoformat(timespec="seconds"),
         exp.isoformat(timespec="seconds")))
    conn.execute("UPDATE copies SET status='зарезервирована' WHERE id=?", (copy_id,))
    conn.commit()
    conn.close()

# =========================================================
#  ОКНО АВТОРИЗАЦИИ
# =========================================================
class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Вход в систему")
        self.geometry("360x220")
        self.resizable(False, False)
        self.current_user = None

        tk.Label(self, text="БиблиоУчет", font=("Arial", 16, "bold")).pack(pady=10)
        frame = tk.Frame(self)
        frame.pack(pady=5)

        tk.Label(frame, text="Логин:").grid(row=0, column=0, sticky="e", pady=4)
        self.ent_login = tk.Entry(frame, width=25)
        self.ent_login.grid(row=0, column=1, pady=4)
        self.ent_login.insert(0, "admin")

        tk.Label(frame, text="Пароль:").grid(row=1, column=0, sticky="e", pady=4)
        self.ent_pass = tk.Entry(frame, width=25, show="*")
        self.ent_pass.grid(row=1, column=1, pady=4)
        self.ent_pass.insert(0, "admin")

        tk.Button(self, text="Войти", width=20, command=self.do_login).pack(pady=12)
        tk.Label(self, text="admin/admin или lib1/1234", fg="gray").pack()

    def do_login(self):
        login = self.ent_login.get().strip()
        pwd = self.ent_pass.get().strip()
        user = check_login(login, pwd)
        if not user:
            messagebox.showerror("Ошибка", "Неверный логин или пароль")
            return
        self.current_user = user
        self.destroy()
        MainWindow(user).mainloop()

# =========================================================
#  ГЛАВНОЕ ОКНО
# =========================================================
class MainWindow(tk.Tk):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.title(APP_TITLE)
        self.geometry("1100x680")

        header = tk.Frame(self, bg="#2c3e50", height=40)
        header.pack(fill="x")
        tk.Label(header, text="Пользователь: " + user["role"],
                 bg="#2c3e50", fg="white", font=("Arial", 11)).pack(side="right", padx=10)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        nb.add(BooksTab(nb), text="Каталог книг")
        nb.add(ReadersTab(nb), text="Читатели")
        nb.add(LoansTab(nb, user), text="Выдача / Возврат")
        nb.add(ReservationsTab(nb), text="Резервирование")
        nb.add(DebtsTab(nb), text="Задолженности")
        nb.add(HistoryTab(nb), text="История")
        nb.add(ReportsTab(nb), text="Отчёты")

        expire_reservations()

# =========================================================
#  КАТАЛОГ
# =========================================================
class BooksTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.build_ui()
        self.load_books()

    def build_ui(self):
        top = tk.Frame(self)
        top.pack(fill="x", padx=5, pady=5)

        tk.Label(top, text="Поиск:").pack(side="left")
        self.ent_search = tk.Entry(top, width=30)
        self.ent_search.pack(side="left", padx=5)
        self.ent_search.bind("<KeyRelease>", lambda e: self.load_books())
        tk.Button(top, text="Добавить книгу", command=self.add_book).pack(side="left", padx=5)
        tk.Button(top, text="Изменить", command=self.edit_book).pack(side="left")
        tk.Button(top, text="Удалить", command=self.del_book).pack(side="left", padx=5)
        tk.Button(top, text="Добавить экземпляр", command=self.add_copy).pack(side="left", padx=5)

        cols = ("id", "isbn", "title", "author", "year", "publisher", "genre")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (40, 110, 200, 150, 60, 120, 100)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=5)

        tk.Label(self, text="Экземпляры выбранной книги:", anchor="w").pack(fill="x", padx=5)
        cols2 = ("id", "inv", "status", "condition")
        self.tree_copies = ttk.Treeview(self, columns=cols2, show="headings", height=5)
        for c, w in zip(cols2, (40, 150, 150, 150)):
            self.tree_copies.heading(c, text=c)
            self.tree_copies.column(c, width=w)
        self.tree_copies.pack(fill="x", padx=5, pady=(0, 8))

        self.tree.bind("<<TreeviewSelect>>", lambda e: self.load_copies())

    def load_books(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = self.ent_search.get().strip().lower()
        conn = get_connection()
        rows = conn.execute("""
            SELECT b.id, b.isbn, b.title, b.author, b.year, b.publisher, g.name
            FROM books b LEFT JOIN genres g ON g.id=b.genre_id
            ORDER BY b.id
        """).fetchall()
        conn.close()
        for r in rows:
            if q and q not in (str(r[2]) + str(r[3])).lower():
                continue
            self.tree.insert("", "end", values=tuple(r))

    def selected_book_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Внимание", "Выберите книгу")
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def load_copies(self):
        for i in self.tree_copies.get_children():
            self.tree_copies.delete(i)
        bid = self.selected_book_id()
        if not bid:
            return
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, inventory_no, status, condition FROM copies WHERE book_id=?", (bid,)
        ).fetchall()
        conn.close()
        for r in rows:
            self.tree_copies.insert("", "end", values=tuple(r))

    def add_book(self):
        BookDialog(self, on_save=self.load_books)

    def edit_book(self):
        bid = self.selected_book_id()
        if not bid:
            return
        conn = get_connection()
        row = conn.execute("SELECT * FROM books WHERE id=?", (bid,)).fetchone()
        conn.close()
        BookDialog(self, on_save=self.load_books, book=row)

    def del_book(self):
        bid = self.selected_book_id()
        if not bid:
            return
        if not messagebox.askyesno("Удаление", "Удалить книгу и все её экземпляры?"):
            return
        conn = get_connection()
        conn.execute("DELETE FROM books WHERE id=?", (bid,))
        conn.commit()
        conn.close()
        self.load_books()
        self.load_copies()

    def add_copy(self):
        bid = self.selected_book_id()
        if not bid:
            return
        inv = simpledialog.askstring("Новый экземпляр", "Инвентарный номер:")
        if not inv:
            return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO copies(book_id, inventory_no) VALUES (?,?)", (bid, inv))
            conn.commit()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
        conn.close()
        self.load_copies()

class BookDialog(tk.Toplevel):
    def __init__(self, parent, on_save, book=None):
        super().__init__(parent)
        self.title("Книга")
        self.geometry("400x320")
        self.on_save = on_save
        self.book = book

        fields = [("ISBN", "isbn"), ("Название", "title"), ("Автор", "author"),
                  ("Год", "year"), ("Издательство", "publisher")]
        self.entries = {}
        for i, item in enumerate(fields):
            label, key = item
            tk.Label(self, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=3)
            e = tk.Entry(self, width=35)
            e.grid(row=i, column=1, padx=5, pady=3)
            self.entries[key] = e

        tk.Label(self, text="Жанр").grid(row=5, column=0, sticky="e")
        conn = get_connection()
        self.genres = conn.execute("SELECT id, name FROM genres").fetchall()
        conn.close()
        self.cb_genre = ttk.Combobox(self, values=[g["name"] for g in self.genres], state="readonly")
        self.cb_genre.grid(row=5, column=1, padx=5, pady=3)

        if book:
            for k in ("isbn", "title", "author", "year", "publisher"):
                self.entries[k].insert(0, book[k] if book[k] is not None else "")
            for g in self.genres:
                if g["id"] == book["genre_id"]:
                    self.cb_genre.set(g["name"])

        tk.Button(self, text="Сохранить", command=self.save).grid(row=6, column=1, pady=10)

    def save(self):
        data = {k: e.get().strip() for k, e in self.entries.items()}
        if not data["title"] or not data["author"]:
            messagebox.showerror("Ошибка", "Название и автор обязательны")
            return
        genre_id = None
        for g in self.genres:
            if g["name"] == self.cb_genre.get():
                genre_id = g["id"]
        year = int(data["year"]) if data["year"].isdigit() else None

        conn = get_connection()
        if self.book:
            conn.execute("UPDATE books SET isbn=?,title=?,author=?,year=?,publisher=?,genre_id=? WHERE id=?",
                         (data["isbn"], data["title"], data["author"], year,
                          data["publisher"], genre_id, self.book["id"]))
        else:
            conn.execute("INSERT INTO books(isbn,title,author,year,publisher,genre_id) VALUES (?,?,?,?,?,?)",
                         (data["isbn"], data["title"], data["author"], year,
                          data["publisher"], genre_id))
        conn.commit()
        conn.close()
        self.on_save()
        self.destroy()

# =========================================================
#  ЧИТАТЕЛИ
# =========================================================
class ReadersTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.build_ui()
        self.load()

    def build_ui(self):
        top = tk.Frame(self)
        top.pack(fill="x", padx=5, pady=5)
        tk.Button(top, text="Добавить читателя", command=self.add).pack(side="left")
        tk.Button(top, text="Удалить", command=self.del_reader).pack(side="left", padx=5)

        cols = ("id", "card_no", "full_name", "phone", "category")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c, w in zip(cols, (40, 100, 250, 150, 150)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

    def load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        conn = get_connection()
        rows = conn.execute("""
            SELECT r.id, r.card_no, r.full_name, r.phone, c.name
            FROM readers r LEFT JOIN categories c ON c.id=r.category_id
            ORDER BY r.id
        """).fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", "end", values=tuple(r))

    def add(self):
        card = simpledialog.askstring("Читатель", "Номер билета:")
        if not card:
            return
        name = simpledialog.askstring("Читатель", "ФИО:")
        if not name:
            return
        phone = simpledialog.askstring("Читатель", "Телефон:") or ""
        conn = get_connection()
        try:
            conn.execute("INSERT INTO readers(card_no, full_name, phone, category_id) VALUES (?,?,?,1)",
                         (card, name, phone))
            conn.commit()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
        conn.close()
        self.load()

    def del_reader(self):
        sel = self.tree.selection()
        if not sel:
            return
        rid = int(self.tree.item(sel[0])["values"][0])
        conn = get_connection()
        active = conn.execute(
            "SELECT COUNT(*) FROM loans WHERE reader_id=? AND return_date IS NULL", (rid,)
        ).fetchone()[0]
        if active:
            messagebox.showerror("Ошибка", "У читателя есть невозвращённые книги")
            conn.close()
            return
        conn.execute("DELETE FROM readers WHERE id=?", (rid,))
        conn.commit()
        conn.close()
        self.load()

# =========================================================
#  ВЫДАЧА / ВОЗВРАТ
# =========================================================
class LoansTab(tk.Frame):
    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.build_ui()
        self.load()

    def build_ui(self):
        form = tk.LabelFrame(self, text="Оформить выдачу", padx=10, pady=10)
        form.pack(fill="x", padx=10, pady=10)

        tk.Label(form, text="Номер билета:").grid(row=0, column=0, sticky="e")
        self.ent_card = tk.Entry(form, width=20)
        self.ent_card.grid(row=0, column=1, padx=5)

        tk.Label(form, text="Инв. номер:").grid(row=0, column=2, sticky="e")
        self.ent_inv = tk.Entry(form, width=20)
        self.ent_inv.grid(row=0, column=3, padx=5)

        tk.Label(form, text="Срок (дней):").grid(row=0, column=4, sticky="e")
        self.ent_days = tk.Entry(form, width=6)
        self.ent_days.insert(0, "14")
        self.ent_days.grid(row=0, column=5, padx=5)

        tk.Button(form, text="Выдать", command=self.issue).grid(row=0, column=6, padx=10)

        tk.Label(self, text="Активные выдачи:", anchor="w").pack(fill="x", padx=10)
        cols = ("loan_id", "reader", "book", "inv", "issue", "due")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c, w in zip(cols, (70, 200, 220, 100, 100, 100)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=10)
        tk.Button(self, text="Оформить возврат", command=self.return_book).pack(pady=10)

    def load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        conn = get_connection()
        rows = conn.execute("""
            SELECT l.id, r.full_name, b.title, c.inventory_no, l.issue_date, l.due_date
            FROM loans l
            JOIN readers r ON r.id=l.reader_id
            JOIN copies c  ON c.id=l.copy_id
            JOIN books b   ON b.id=c.book_id
            WHERE l.return_date IS NULL
            ORDER BY l.due_date
        """).fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", "end", values=tuple(r))

    def issue(self):
        card = self.ent_card.get().strip()
        inv = self.ent_inv.get().strip()
        days = self.ent_days.get().strip()
        if not card or not inv or not days.isdigit():
            messagebox.showerror("Ошибка", "Заполните все поля корректно")
            return
        days = int(days)

        conn = get_connection()
        reader = conn.execute("SELECT id FROM readers WHERE card_no=? AND is_active=1", (card,)).fetchone()
        if not reader:
            messagebox.showerror("Ошибка", "Читатель не найден")
            conn.close()
            return
        if has_open_debt(reader["id"]):
            messagebox.showerror("Отказ", "У читателя есть непогашенная задолженность")
            conn.close()
            return

        copy = conn.execute("SELECT id, status FROM copies WHERE inventory_no=?", (inv,)).fetchone()
        if not copy:
            messagebox.showerror("Ошибка", "Экземпляр не найден")
            conn.close()
            return

        # проверка резерва
        if copy["status"] == "зарезервирована":
            res = conn.execute(
                "SELECT reader_id FROM reservations WHERE copy_id=? AND status='активна'",
                (copy["id"],)).fetchone()
            if not res or res["reader_id"] != reader["id"]:
                messagebox.showerror("Отказ", "Экземпляр зарезервирован другим читателем")
                conn.close()
                return
            # отдаём бронь
            conn.execute("UPDATE reservations SET status='выдана' WHERE copy_id=? AND status='активна'",
                         (copy["id"],))
        elif copy["status"] != "в наличии":
            messagebox.showerror("Ошибка", "Экземпляр недоступен (статус: " + copy["status"] + ")")
            conn.close()
            return

        issue = date.today()
        due = issue + timedelta(days=days)
        conn.execute("INSERT INTO loans(copy_id, reader_id, librarian_id, issue_date, due_date) VALUES (?,?,?,?,?)",
                     (copy["id"], reader["id"], self.user["id"],
                      issue.isoformat(), due.isoformat()))
        conn.execute("UPDATE copies SET status='выдан' WHERE id=?", (copy["id"],))
        conn.commit()
        conn.close()
        messagebox.showinfo("Готово", "Книга выдана. Срок возврата: " + due.isoformat())
        self.load()

    def return_book(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Внимание", "Выберите выдачу")
            return
        loan_id = int(self.tree.item(sel[0])["values"][0])
        conn = get_connection()
        loan = conn.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone()
        today = date.today()
        due = date.fromisoformat(loan["due_date"])

        conn.execute("UPDATE loans SET return_date=? WHERE id=?", (today.isoformat(), loan_id))
        conn.execute("UPDATE copies SET status='в наличии' WHERE id=?", (loan["copy_id"],))

        msg = "Книга возвращена."
        if today > due:
            days = (today - due).days
            amount = calc_fine(days)
            conn.execute("INSERT INTO debts(loan_id, reader_id, type, days_overdue, amount) VALUES (?,?,?,?,?)",
                         (loan_id, loan["reader_id"], "просрочка", days, amount))
            msg += "\nПросрочка " + str(days) + " дн. Штраф: " + format(amount, '.2f') + " руб."
        conn.commit()
        conn.close()
        messagebox.showinfo("Возврат", msg)
        self.load()

# =========================================================
#  РЕЗЕРВИРОВАНИЕ
# =========================================================
class ReservationsTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.build_ui()
        self.load()

    def build_ui(self):
        form = tk.LabelFrame(self, text="Забронировать экземпляр", padx=10, pady=10)
        form.pack(fill="x", padx=10, pady=10)

        tk.Label(form, text="Номер билета:").grid(row=0, column=0, sticky="e")
        self.ent_card = tk.Entry(form, width=20)
        self.ent_card.grid(row=0, column=1, padx=5)

        tk.Label(form, text="Инв. номер:").grid(row=0, column=2, sticky="e")
        self.ent_inv = tk.Entry(form, width=20)
        self.ent_inv.grid(row=0, column=3, padx=5)

        tk.Button(form, text="Зарезервировать", command=self.reserve).grid(row=0, column=4, padx=10)

        tk.Button(self, text="Обновить / снять истёкшие", command=self.refresh).pack(pady=5)

        tk.Label(self, text="Активные брони:", anchor="w").pack(fill="x", padx=10)
        cols = ("id", "reader", "book", "inv", "created", "expires", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c, w in zip(cols, (40, 200, 200, 100, 130, 130, 100)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=10)
        tk.Button(self, text="Отменить бронь", command=self.cancel).pack(pady=10)

    def refresh(self):
        expire_reservations()
        self.load()

    def load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        conn = get_connection()
        rows = conn.execute("""
            SELECT res.id, r.full_name, b.title, c.inventory_no,
                   res.created_at, res.expires_at, res.status
            FROM reservations res
            JOIN readers r ON r.id=res.reader_id
            JOIN copies c  ON c.id=res.copy_id
            JOIN books b   ON b.id=c.book_id
            ORDER BY res.status, res.expires_at
        """).fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", "end", values=tuple(r))

    def reserve(self):
        card = self.ent_card.get().strip()
        inv = self.ent_inv.get().strip()
        if not card or not inv:
            messagebox.showerror("Ошибка", "Заполните поля")
            return
        conn = get_connection()
        reader = conn.execute("SELECT id FROM readers WHERE card_no=?", (card,)).fetchone()
        if not reader:
            messagebox.showerror("Ошибка", "Читатель не найден")
            conn.close()
            return
        if has_open_debt(reader["id"]):
            messagebox.showerror("Отказ", "Есть непогашенная задолженность")
            conn.close()
            return
        copy = conn.execute("SELECT id, status FROM copies WHERE inventory_no=?", (inv,)).fetchone()
        if not copy:
            messagebox.showerror("Ошибка", "Экземпляр не найден")
            conn.close()
            return
        if copy["status"] in ("списан", "зарезервирована"):
            messagebox.showerror("Ошибка", "Экземпляр нельзя зарезервировать (статус: " + copy["status"] + ")")
            conn.close()
            return
        conn.close()
        create_reservation(copy["id"], reader["id"])
        messagebox.showinfo("Готово", "Бронь создана на " + get_setting("reserve_days", "3") + " дн.")
        self.load()

    def cancel(self):
        sel = self.tree.selection()
        if not sel:
            return
        rid = int(self.tree.item(sel[0])["values"][0])
        conn = get_connection()
        row = conn.execute("SELECT copy_id FROM reservations WHERE id=?", (rid,)).fetchone()
        conn.execute("UPDATE reservations SET status='отменена' WHERE id=?", (rid,))
        conn.execute("UPDATE copies SET status='в наличии' WHERE id=? AND status='зарезервирована'",
                     (row["copy_id"],))
        conn.commit()
        conn.close()
        self.load()

# =========================================================
#  ЗАДОЛЖЕННОСТИ
# =========================================================
class DebtsTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        cols = ("id", "reader", "book", "type", "days", "amount", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c, w in zip(cols, (40, 200, 220, 100, 70, 90, 100)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Button(self, text="Погасить задолженность", command=self.close_debt).pack(pady=5)
        self.load()

    def load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        conn = get_connection()
        rows = conn.execute("""
            SELECT r.full_name, r.card_no, b.title, c.inventory_no,
                   l.issue_date, l.due_date, d.days_overdue, d.amount, d.status
            FROM debts d
            JOIN readers r      ON r.id = d.reader_id
            JOIN categories cat ON cat.id = r.category_id
            JOIN loans l        ON l.id = d.loan_id
            JOIN copies c       ON c.id = l.copy_id
            JOIN books b        ON b.id = c.book_id
            WHERE cat.name = 'Студент'
            ORDER BY d.amount DESC, r.full_name
        """).fetchall()

        total = conn.execute("""
            SELECT COUNT(DISTINCT r.id), COALESCE(SUM(d.amount), 0)
            FROM debts d
            JOIN readers r      ON r.id = d.reader_id
            JOIN categories cat ON cat.id = r.category_id
            WHERE cat.name = 'Студент' AND d.status = 'открыта'
        """).fetchone()
        conn.close()

        if not rows:
            messagebox.showinfo("Отчёт", "Задолженностей по студентам нет")
            return

        total_row = ["ИТОГО", "", "", "", "", "", "", round(total[1], 2),
                     "должников: " + str(total[0])]
        all_rows = [tuple(r) for r in rows] + [tuple(total_row)]
        self._export(
            all_rows,
            ["ФИО", "Билет", "Книга", "Инв.", "Выдана", "Срок",
             "Дней просрочки", "Сумма", "Статус"],
            "students_debts.csv",
        )

if __name__ == "__main__":
    init_db()
    LoginWindow().mainloop()