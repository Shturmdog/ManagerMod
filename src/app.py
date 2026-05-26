from flask import Flask, render_template, request, redirect, url_for, flash, g
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

DATABASE = 'DataBase.db'

login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ============ DATABASE HELPERS ============

def get_db():
    """Получение соединения с БД"""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Закрытие соединения после запроса"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False, commit=False):
    """Универсальная функция для выполнения SQL-запросов"""
    db = get_db()
    cur = db.execute(query, args)

    if commit:
        db.commit()
        lastrowid = cur.lastrowid
        cur.close()
        return lastrowid

    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def dict_from_row(row):
    """Конвертирует sqlite3.Row в обычный dict с конвертацией дат"""
    if row is None:
        return None
    d = {}
    for key in row.keys():
        val = row[key]
        # Конвертируем строки дат в datetime
        if isinstance(val, str) and key in ('created_at', 'updated_at', 'start_time', 'end_time', 'approved_at'):
            for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                try:
                    val = datetime.strptime(val, fmt)
                    break
                except ValueError:
                    continue
        d[key] = val
    return d


def query_db_dict(query, args=(), one=False, commit=False):
    """Версия query_db, возвращающая dict'ы с конвертированными датами"""
    result = query_db(query, args, one, commit)
    if commit:
        return result
    if one:
        return dict_from_row(result)
    return [dict_from_row(row) for row in result]


def init_db():
    """Инициализация базы данных — создание таблиц"""
    db = sqlite3.connect(DATABASE)

    db.executescript("""
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS menu_items;
        DROP TABLE IF EXISTS shifts;
        DROP TABLE IF EXISTS tables;
        DROP TABLE IF EXISTS categories;
        DROP TABLE IF EXISTS users;

        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(80) UNIQUE NOT NULL,
            password_hash VARCHAR(200) NOT NULL,
            role VARCHAR(20) DEFAULT 'user'
        );

        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(50) UNIQUE NOT NULL
        );

        CREATE TABLE tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number INTEGER UNIQUE NOT NULL,
            capacity INTEGER DEFAULT 2,
            status VARCHAR(20) DEFAULT 'free'
        );

        CREATE TABLE menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            price REAL NOT NULL,
            category VARCHAR(50) DEFAULT 'main',
            is_available BOOLEAN DEFAULT 1,
            is_approved BOOLEAN DEFAULT 0,
            created_by INTEGER NOT NULL,
            approved_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            approved_at DATETIME,
            category_id INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (approved_by) REFERENCES users(id),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            waiter_id INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'waiting',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            table_number INTEGER NOT NULL,
            table_id INTEGER,
            FOREIGN KEY (waiter_id) REFERENCES users(id),
            FOREIGN KEY (table_id) REFERENCES tables(id)
        );

        CREATE TRIGGER update_orders_timestamp 
        AFTER UPDATE ON orders
        FOR EACH ROW
        BEGIN
            UPDATE orders SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;

        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            menu_item_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
        );

        CREATE TABLE shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            end_time DATETIME,
            closed_by INTEGER,
            total_revenue REAL DEFAULT 0.0,
            best_dish VARCHAR(100),
            best_waiter VARCHAR(80),
            best_waiter_id INTEGER,
            FOREIGN KEY (closed_by) REFERENCES users(id),
            FOREIGN KEY (best_waiter_id) REFERENCES users(id)
        );

        CREATE INDEX idx_orders_waiter ON orders(waiter_id);
        CREATE INDEX idx_orders_status ON orders(status);
        CREATE INDEX idx_orders_table ON orders(table_number);
        CREATE INDEX idx_menu_items_category ON menu_items(category_id);
        CREATE INDEX idx_menu_items_created_by ON menu_items(created_by);
        CREATE INDEX idx_order_items_order ON order_items(order_id);
        CREATE INDEX idx_shifts_end_time ON shifts(end_time);
    """)
    db.commit()
    db.close()


# ============ USER CLASS FOR FLASK-LOGIN ============

class User(UserMixin):
    def __init__(self, id, username, password_hash, role):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    row = query_db("SELECT * FROM users WHERE id = ?", [user_id], one=True)
    if row:
        return User(row['id'], row['username'], row['password_hash'], row['role'])
    return None


# ============ INIT DATABASE ============

if not os.path.exists(DATABASE):
    init_db()

    db = sqlite3.connect(DATABASE)
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ('admin', generate_password_hash('admin123'), 'admin')
    )
    db.commit()
    db.close()


# ============ JINJA FILTERS ============

@app.template_filter('datetime')
def format_datetime(value, fmt='%d.%m.%Y %H:%M'):
    """Фильтр для форматирования дат в шаблонах"""
    if value is None:
        return ''
    if isinstance(value, str):
        for f in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                value = datetime.strptime(value, f)
                break
            except ValueError:
                continue
        else:
            return value
    if isinstance(value, datetime):
        return value.strftime(fmt)
    return str(value)


# ============ AUTH ROUTES ============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        row = query_db("SELECT * FROM users WHERE username = ?", [username], one=True)

        if row and check_password_hash(row['password_hash'], password):
            user = User(row['id'], row['username'], row['password_hash'], row['role'])
            login_user(user)

            if user.role == 'admin':
                return redirect(url_for('admin'))
            elif user.role == 'cook':
                return redirect(url_for('cook_dashboard'))
            elif user.role == 'waiter':
                return redirect(url_for('waiter_dashboard'))
            elif user.role == 'manager':
                return redirect(url_for('manager_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Неверное имя или пароль', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ============ ADMIN ROUTES ============

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    users = query_db_dict("SELECT * FROM users")
    return render_template('admin.html', users=users)


@app.route('/admin/create_user', methods=['POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        return "Forbidden", 403

    username = request.form['username']
    password = request.form['password']
    role = request.form.get('role', 'user')

    existing = query_db("SELECT id FROM users WHERE username = ?", [username], one=True)
    if existing:
        flash('Пользователь с таким именем уже существует', 'danger')
    else:
        query_db(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            [username, generate_password_hash(password), role],
            commit=True
        )
        flash(f'Пользователь {username} создан', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return "Forbidden", 403

    if user_id == current_user.id:
        flash("Вы не можете удалять самого себя", 'danger')
        return redirect(url_for('admin'))

    user = query_db("SELECT username FROM users WHERE id = ?", [user_id], one=True)
    if user:
        query_db("DELETE FROM users WHERE id = ?", [user_id], commit=True)
        flash(f'Пользователь "{user["username"]}" удалён', 'success')
    return redirect(url_for('admin'))


# ============ MANAGER ROUTES ============

@app.route('/manager/dashboard')
@login_required
def manager_dashboard():
    if current_user.role != 'manager':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    pending_items = query_db_dict("""
        SELECT mi.*, u.username as creator_name 
        FROM menu_items mi 
        JOIN users u ON mi.created_by = u.id 
        WHERE mi.is_approved = 0
    """)
    active_shift = query_db_dict("SELECT * FROM shifts WHERE end_time IS NULL", one=True)
    return render_template('manager_dashboard.html', pending_items=pending_items, active_shift=active_shift)


@app.route('/manager_dashboard/approve_item/<int:item_id>', methods=['POST'])
@login_required
def approve_item(item_id):
    if current_user.role != 'manager':
        return "Forbidden", 403

    query_db("""
        UPDATE menu_items 
        SET is_approved = 1, approved_by = ?, approved_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    """, [current_user.id, item_id], commit=True)

    item = query_db("SELECT name FROM menu_items WHERE id = ?", [item_id], one=True)
    flash(f'Блюдо "{item["name"]}" утверждено', 'success')
    return redirect(url_for('manager_dashboard'))


@app.route('/manager_dashboard/reject_item/<int:item_id>', methods=['POST'])
@login_required
def reject_item(item_id):
    if current_user.role != 'manager':
        return "Forbidden", 403

    item = query_db("SELECT name FROM menu_items WHERE id = ?", [item_id], one=True)
    if item:
        query_db("DELETE FROM menu_items WHERE id = ?", [item_id], commit=True)
        flash(f'Блюдо "{item["name"]}" отклонено и удалено', 'warning')
    return redirect(url_for('manager_dashboard'))


@app.route('/manager_dashboard/shift_stats')
@login_required
def shift_stats():
    if current_user.role != 'manager':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    shifts = query_db_dict("""
        SELECT s.*, u.username as closer_name, bw.username as best_waiter_name
        FROM shifts s
        LEFT JOIN users u ON s.closed_by = u.id
        LEFT JOIN users bw ON s.best_waiter_id = bw.id
        WHERE s.end_time IS NOT NULL
        ORDER BY s.end_time DESC
    """)
    return render_template('shift_stats.html', shifts=shifts)


@app.route('/manager_dashboard/open_shift', methods=['POST'])
@login_required
def open_shift():
    if current_user.role != 'manager':
        return "Forbidden", 403

    active = query_db("SELECT id FROM shifts WHERE end_time IS NULL", one=True)
    if active:
        flash('Смена уже открыта', 'warning')
    else:
        query_db("INSERT INTO shifts (start_time) VALUES (CURRENT_TIMESTAMP)", commit=True)
        flash('Новая смена открыта', 'success')
    return redirect(url_for('manager_dashboard'))


def get_shift_statistics():
    """Получение статистики смены через SQL"""
    total = query_db("""
        SELECT COALESCE(SUM(mi.price * oi.quantity), 0) as revenue
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN menu_items mi ON oi.menu_item_id = mi.id
        WHERE o.status = 'completed'
    """, one=True)

    best_dish = query_db("""
        SELECT mi.name, SUM(oi.quantity) as qty
        FROM order_items oi
        JOIN menu_items mi ON oi.menu_item_id = mi.id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status = 'completed'
        GROUP BY mi.name
        ORDER BY qty DESC
        LIMIT 1
    """, one=True)

    best_waiter = query_db("""
        SELECT u.username, SUM(mi.price * oi.quantity) as revenue
        FROM orders o
        JOIN users u ON o.waiter_id = u.id
        JOIN order_items oi ON o.id = oi.order_id
        JOIN menu_items mi ON oi.menu_item_id = mi.id
        WHERE o.status = 'completed'
        GROUP BY u.username
        ORDER BY revenue DESC
        LIMIT 1
    """, one=True)

    return (
        total['revenue'] if total else 0.0,
        best_dish['name'] if best_dish else None,
        best_waiter['username'] if best_waiter else None
    )


@app.route('/manager_dashboard/close_shift', methods=['POST'])
@login_required
def close_shift():
    if current_user.role != 'manager':
        return "Forbidden", 403

    active_shift = query_db("SELECT * FROM shifts WHERE end_time IS NULL", one=True)

    if not active_shift:
        query_db("INSERT INTO shifts (start_time) VALUES (CURRENT_TIMESTAMP)", commit=True)
        active_shift = query_db("SELECT * FROM shifts WHERE end_time IS NULL", one=True)

    total_revenue, best_dish, best_waiter = get_shift_statistics()

    best_waiter_id = None
    if best_waiter:
        bw = query_db("SELECT id FROM users WHERE username = ?", [best_waiter], one=True)
        if bw:
            best_waiter_id = bw['id']

    query_db("""
        UPDATE shifts 
        SET end_time = CURRENT_TIMESTAMP,
            closed_by = ?,
            total_revenue = ?,
            best_dish = ?,
            best_waiter = ?,
            best_waiter_id = ?
        WHERE id = ?
    """, [current_user.id, total_revenue, best_dish, best_waiter, best_waiter_id, active_shift['id']], commit=True)

    query_db("DELETE FROM orders WHERE status = 'completed'", commit=True)

    flash(f'Смена закрыта. Выручка: {total_revenue} руб., лучшее блюдо: {best_dish}, лучший официант: {best_waiter}',
          'success')
    return redirect(url_for('manager_dashboard'))


# ============ COOK ROUTES ============

@app.route('/cook/dashboard')
@login_required
def cook_dashboard():
    if current_user.role not in ['cook', 'admin']:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    dishes = query_db_dict("SELECT * FROM menu_items WHERE created_by = ?", [current_user.id])

    waiting_orders = query_db_dict("""
        SELECT o.*, u.username as waiter_name
        FROM orders o
        JOIN users u ON o.waiter_id = u.id
        WHERE o.status = 'waiting'
        ORDER BY o.created_at ASC
    """)

    cooking_orders = query_db_dict("""
        SELECT o.*, u.username as waiter_name
        FROM orders o
        JOIN users u ON o.waiter_id = u.id
        WHERE o.status = 'cooking'
        ORDER BY o.created_at ASC
    """)

    ready_orders = query_db_dict("""
        SELECT o.*, u.username as waiter_name
        FROM orders o
        JOIN users u ON o.waiter_id = u.id
        WHERE o.status = 'ready'
        ORDER BY o.updated_at DESC
    """)

    active_shift = query_db_dict("SELECT * FROM shifts WHERE end_time IS NULL", one=True)

    return render_template('cook_dashboard.html',
                           dishes=dishes,
                           waiting_orders=waiting_orders,
                           cooking_orders=cooking_orders,
                           ready_orders=ready_orders,
                           active_shift=active_shift)


@app.route('/cook/create_menu', methods=['GET', 'POST'])
@login_required
def create_menu():
    if current_user.role not in ['cook', 'admin']:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        category = request.form.get('category', 'main')

        if not name or not price:
            flash('Название и цена обязательны', 'danger')
            return redirect(url_for('create_menu'))

        try:
            price = float(price)
        except ValueError:
            flash('Цена должна быть числом', 'danger')
            return redirect(url_for('create_menu'))

        query_db("""
            INSERT INTO menu_items (name, price, category, created_by, is_approved)
            VALUES (?, ?, ?, ?, 0)
        """, [name, price, category, current_user.id], commit=True)

        flash(f'Блюдо "{name}" добавлено на утверждение', 'success')
        return redirect(url_for('cook_dashboard'))

    return render_template('create_menu.html')


@app.route('/cook/start_cooking/<int:order_id>', methods=['POST'])
@login_required
def start_cooking(order_id):
    if current_user.role not in ['cook', 'admin']:
        return "Forbidden", 403

    active_shift = query_db("SELECT id FROM shifts WHERE end_time IS NULL", one=True)
    if not active_shift:
        flash('Смена закрыта. Нельзя начать приготовление.', 'danger')
        return redirect(url_for('cook_dashboard'))

    order = query_db("SELECT status FROM orders WHERE id = ?", [order_id], one=True)
    if order and order['status'] == 'waiting':
        query_db("UPDATE orders SET status = 'cooking' WHERE id = ?", [order_id], commit=True)
        flash(f'Заказ №{order_id} начат приготовление', 'info')
    else:
        flash('Невозможно начать готовку', 'warning')
    return redirect(url_for('cook_dashboard'))


@app.route('/cook/mark_ready/<int:order_id>', methods=['POST'])
@login_required
def mark_ready(order_id):
    if current_user.role not in ['cook', 'admin']:
        return "Forbidden", 403

    active_shift = query_db("SELECT id FROM shifts WHERE end_time IS NULL", one=True)
    if not active_shift:
        flash('Смена закрыта. Нельзя отметить готовность.', 'danger')
        return redirect(url_for('cook_dashboard'))

    order = query_db("SELECT status FROM orders WHERE id = ?", [order_id], one=True)
    if order and order['status'] in ['waiting', 'cooking']:
        query_db("UPDATE orders SET status = 'ready' WHERE id = ?", [order_id], commit=True)
        flash(f'Заказ №{order_id} готов к выдаче', 'success')
    else:
        flash('Некорректный статус', 'warning')
    return redirect(url_for('cook_dashboard'))


@app.route('/cook/toggle_availability/<int:item_id>', methods=['POST'])
@login_required
def toggle_availability(item_id):
    if current_user.role != 'cook':
        return "Forbidden", 403

    item = query_db("SELECT name, is_available FROM menu_items WHERE id = ?", [item_id], one=True)
    if item:
        new_status = 0 if item['is_available'] else 1
        query_db("UPDATE menu_items SET is_available = ? WHERE id = ?", [new_status, item_id], commit=True)
        status_text = "Доступно" if new_status else "Недоступно"
        flash(f'Блюдо "{item["name"]}" теперь {status_text}', 'success')
    return redirect(url_for('cook_dashboard'))


# ============ WAITER ROUTES ============

@app.route('/waiter/dashboard')
@login_required
def waiter_dashboard():
    if current_user.role != 'waiter':
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    menu_items = query_db_dict("SELECT * FROM menu_items WHERE is_approved = 1 AND is_available = 1")
    active_shift = query_db_dict("SELECT * FROM shifts WHERE end_time IS NULL", one=True)
    return render_template('waiter_dashboard.html', menu_items=menu_items, active_shift=active_shift)


@app.route('/waiter/create_order', methods=['POST'])
@login_required
def create_order():
    if current_user.role != 'waiter':
        return 'Forbidden', 403

    active_shift = query_db("SELECT id FROM shifts WHERE end_time IS NULL", one=True)
    if not active_shift:
        flash('Смена закрыта. Нельзя создать заказ.', 'danger')
        return redirect(url_for('waiter_dashboard'))

    table_number = request.form.get('table_number')
    if not table_number:
        flash('Не указан номер столика', 'danger')
        return redirect(url_for('waiter_dashboard'))

    items = {}
    for key in request.form:
        if key.startswith('qty_'):
            menu_item_id = int(key.split('_')[1])
            qty = int(request.form[key])
            if qty > 0:
                items[menu_item_id] = qty

    if not items:
        flash('Не выбрано ни одно блюдо', 'danger')
        return redirect(url_for('waiter_dashboard'))

    for menu_item_id in items:
        item = query_db("SELECT name, is_available, is_approved FROM menu_items WHERE id = ?", [menu_item_id], one=True)
        if not item or not item['is_available'] or not item['is_approved']:
            flash(f'Блюдо {item["name"] if item else "?"} больше недоступно', 'danger')
            return redirect(url_for('waiter_dashboard'))

    order_id = query_db(
        "INSERT INTO orders (waiter_id, table_number, status) VALUES (?, ?, 'waiting')",
        [current_user.id, int(table_number)],
        commit=True
    )

    for menu_item_id, quantity in items.items():
        query_db(
            "INSERT INTO order_items (order_id, menu_item_id, quantity) VALUES (?, ?, ?)",
            [order_id, menu_item_id, quantity],
            commit=True
        )

    flash(f'Заказ №{order_id} создан для стола {table_number} и отправлен повару', 'success')
    return redirect(url_for('waiter_dashboard'))


@app.route('/waiter/orders')
@login_required
def waiter_orders():
    if current_user.role != 'waiter':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    active_orders = query_db_dict("""
        SELECT o.*, 
               COALESCE((SELECT SUM(mi.price * oi.quantity) 
                        FROM order_items oi 
                        JOIN menu_items mi ON oi.menu_item_id = mi.id 
                        WHERE oi.order_id = o.id), 0) as total_price
        FROM orders o
        WHERE o.waiter_id = ? AND o.status != 'completed'
        ORDER BY o.created_at DESC
    """, [current_user.id])

    completed_orders = query_db_dict("""
        SELECT o.*,
               COALESCE((SELECT SUM(mi.price * oi.quantity) 
                        FROM order_items oi 
                        JOIN menu_items mi ON oi.menu_item_id = mi.id 
                        WHERE oi.order_id = o.id), 0) as total_price
        FROM orders o
        WHERE o.waiter_id = ? AND o.status = 'completed'
        ORDER BY o.created_at DESC
        LIMIT 20
    """, [current_user.id])

    return render_template('waiter_orders.html', active_orders=active_orders, completed_orders=completed_orders)


@app.route('/waiter/complete_order/<int:order_id>', methods=['POST'])
@login_required
def complete_order(order_id):
    if current_user.role != 'waiter':
        return "Forbidden", 403

    order = query_db("SELECT waiter_id, status FROM orders WHERE id = ?", [order_id], one=True)

    if not order:
        flash('Заказ не найден', 'danger')
        return redirect(url_for('waiter_orders'))

    if order['waiter_id'] != current_user.id:
        flash('Это не ваш заказ', 'danger')
        return redirect(url_for('waiter_orders'))

    if order['status'] != 'ready':
        flash('Заказ ещё не готов', 'warning')
        return redirect(url_for('waiter_orders'))

    query_db("UPDATE orders SET status = 'completed' WHERE id = ?", [order_id], commit=True)
    flash(f'Заказ №{order_id} завершён', 'success')
    return redirect(url_for('waiter_orders'))


# ============ COMMON ROUTES ============

@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html', user=current_user)
    else:
        return redirect(url_for('login'))


@app.route('/home')
@login_required
def home():
    return render_template('home.html', user=current_user)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)