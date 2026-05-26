from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from SimpleDB import SimpleDB

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

#The structure of the user table in the database
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')

    #Methods for working with passwords
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), default='main')  # soup, salad, main, dessert
    is_available = db.Column(db.Boolean, default=True)
    is_approved = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    approved_at = db.Column(db.DateTime, nullable=True)

    # связи
    creator = db.relationship('User', foreign_keys=[created_by])
    approver = db.relationship('User', foreign_keys=[approved_by])

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    waiter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='waiting')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    table_number = db.Column(db.Integer, nullable=False)

    waiter = db.relationship('User', foreign_keys=[waiter_id], backref='orders')

    @property
    def total_price(self):
        return sum(item.menu_item.price * item.quantity for item in self.items)

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    order = db.relationship('Order', backref='items')
    menu_item = db.relationship('MenuItem', backref='order_items')

class Shift(db.Model):
    __tablename__ = 'shifts'
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, default=datetime.now)
    end_time = db.Column(db.DateTime, nullable=True)
    closed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    total_revenue = db.Column(db.Float, default=0.0)
    best_dish = db.Column(db.String(100), nullable=True)
    best_waiter = db.Column(db.String(80), nullable=True)
    best_waiter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    closer = db.relationship('User', foreign_keys=[closed_by])
    best_waiter_rel = db.relationship('User', foreign_keys=[best_waiter_id])

def get_shift_statistics():
    completed_orders = Order.query.filter_by(status='completed').all()
    if not completed_orders:
        return 0.0, None, None

    total_revenue = sum(order.total_price for order in completed_orders)

    dish_count = {}
    for order in completed_orders:
        for item in order.items:
            dish_name = item.menu_item.name
            dish_count[dish_name] = dish_count.get(dish_name, 0) + item.quantity
    best_dish = max(dish_count, key=dish_count.get) if dish_count else None

    waiter_revenue = {}
    for order in completed_orders:
        waiter_name = order.waiter.username
        waiter_revenue[waiter_name] = waiter_revenue.get(waiter_name, 0) + order.total_price
    best_waiter = max(waiter_revenue, key=waiter_revenue.get) if waiter_revenue else None

    return total_revenue, best_dish, best_waiter


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#Create tables and add a test admin
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

#login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
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

#Logout of the system
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

#The administrator's page
@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    users = User.query.all()
    return render_template('admin.html', users=users)

#Creating a new user
@app.route('/admin/create_user', methods=['POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        return "Forbidden", 403
    username = request.form['username']
    password = request.form['password']
    role = request.form.get('role', 'user')

    if User.query.filter_by(username=username).first():
        flash('Пользователь с таким именем уже существует', 'danger')
    else:
        new_user = User(username=username, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash(f'Пользователь {username} создан', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return "Forbidden", 403

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Вы не можете удалять самого себя", 'danger')
        return redirect(url_for('admin'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь "{username}" удалён', 'success')
    return redirect(url_for('admin'))

#Manager
@app.route('/manager/dashboard')
@login_required
def manager_dashboard():
    if current_user.role != 'manager':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    pending_items = MenuItem.query.filter_by(is_approved=False).all()
    active_shift = Shift.query.filter_by(end_time=None).first()
    return render_template('manager_dashboard.html', pending_items=pending_items, active_shift=active_shift)

@app.route('/manager/pending_menu')
@login_required
def pending_menu():
    if current_user.role != 'manager':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    pending_items = MenuItem.query.filter_by(is_approved=False).all()
    return render_template('pending_menu.html', items=pending_items)

@app.route('/manager/approve_item/<int:item_id>', methods=['POST'])
@login_required
def approve_item(item_id):
    if current_user.role != 'manager':
        return "Forbidden", 403

    item = MenuItem.query.get_or_404(item_id)
    item.is_approved = True
    item.approved_by = current_user.id
    item.approved_at = db.func.now()
    db.session.commit()
    flash(f'Блюдо "{item.name}" утверждено', 'success')
    return redirect(url_for('pending_menu'))

#Cook
@app.route('/cook/dashboard')
@login_required
def cook_dashboard():
    if current_user.role not in ['cook', 'admin']:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    dishes = MenuItem.query.filter_by(created_by=current_user.id).all()

    waiting_orders = Order.query.filter_by(status='waiting').order_by(Order.created_at.asc()).all()
    cooking_orders = Order.query.filter_by(status='cooking').order_by(Order.created_at.asc()).all()
    ready_orders = Order.query.filter_by(status='ready').order_by(Order.updated_at.desc()).all()

    return render_template('cook_dashboard.html',
                           dishes=dishes,
                           waiting_orders=waiting_orders,
                           cooking_orders=cooking_orders,
                           ready_orders=ready_orders)


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

        # Используем SQLAlchemy для сохранения блюда
        new_item = MenuItem(
            name=name,
            price=price,
            category=category,
            created_by=current_user.id,
            is_approved=False
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f'Блюдо "{name}" добавлено на утверждение', 'success')
        return redirect(url_for('cook_dashboard'))

    return render_template('create_menu.html')

@app.route('/cook/start_cooking/<int:order_id>', methods=['POST'])
@login_required
def start_cooking(order_id):
    if current_user.role not in ['cook', 'admin']:
        return "Forbidden", 403
    order = Order.query.get_or_404(order_id)
    if order.status == 'waiting':
        order.status = 'cooking'
        db.session.commit()
        flash(f'Заказ №{order.id} начат приготовление', 'info')
    else:
        flash('Невозможно начать готовку', 'warning')
    return redirect(url_for('cook_dashboard'))

@app.route('/cook/mark_ready/<int:order_id>', methods=['POST'])
@login_required
def mark_ready(order_id):
    if current_user.role not in ['cook', 'admin']:
        return "Forbidden", 403
    order = Order.query.get_or_404(order_id)
    if order.status in ['waiting', 'cooking']:
        order.status = 'ready'
        db.session.commit()
        flash(f'Заказ №{order.id} готов к выдаче', 'success')
    else:
        flash('Некорректный статус', 'warning')
    return redirect(url_for('cook_dashboard'))

@app.route('/cook/toggle_availability/<int:item_id>', methods=['POST'])
@login_required
def toggle_availability(item_id):
    if current_user.role not in 'cook':
        return "Forbidden", 403
    item = MenuItem.query.get_or_404(item_id)

    item.is_available = not item.is_available
    db.session.commit()

    status = "Доступно" if item.is_available else "Недоступно"
    flash(f'Блюдо "{item.name}" теперь {status}', 'success')
    return redirect(url_for('cook_dashboard'))


@app.route('/waiter/dashboard')
@login_required
def waiter_dashboard():
    if current_user.role != 'waiter':
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    menu_items = MenuItem.query.filter_by(is_approved=True, is_available=True).all()
    return render_template('waiter_dashboard.html', menu_items=menu_items)

@app.route('/waiter/create_order', methods=['POST'])
@login_required
def create_order():
    if current_user.role != 'waiter':
        return 'Forbidden', 403

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

    for menu_item_id, quantity in items.items():
        menu_item = MenuItem.query.get(menu_item_id)
        if not menu_item or not menu_item.is_available or not menu_item.is_approved:
            flash(f'Блюдо {menu_item.name if menu_item else "?"} больше недоступно', 'danger')
            db.session.rollback()
            return redirect(url_for('waiter_dashboard'))

    order = Order(waiter_id=current_user.id, table_number=int(table_number), status='waiting')
    db.session.add(order)
    db.session.commit()

    for menu_item_id, quantity in items.items():
        order_item = OrderItem(order_id=order.id, menu_item_id=menu_item_id, quantity=quantity)
        db.session.add(order_item)

    db.session.commit()
    flash(f'Заказ №{order.id} создан для стола {table_number} и отправлен повару', 'success')
    return redirect(url_for('waiter_dashboard'))

@app.route('/waiter/orders')
@login_required
def waiter_orders():
    if current_user.role != 'waiter':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    active_orders = Order.query.filter(Order.waiter_id == current_user.id, Order.status != 'completed').order_by(Order.created_at.desc()).all()
    completed_orders = Order.query.filter(Order.waiter_id == current_user.id, Order.status == 'completed').order_by(Order.created_at.desc()).limit(20).all()
    return render_template('waiter_orders.html', active_orders=active_orders, completed_orders=completed_orders)

@app.route('/waiter/complete_order/<int:order_id>', methods=['POST'])
@login_required
def complete_order(order_id):
    if current_user.role != 'waiter':
        return "Forbidden", 403
    order = Order.query.get_or_404(order_id)
    if order.waiter_id != current_user.id:
        flash('Это не ваш заказ', 'danger')
        return redirect(url_for('waiter_orders'))
    if order.status != 'ready':
        flash('Заказ ещё не готов', 'warning')
        return redirect(url_for('waiter_orders'))
    order.status = 'completed'
    db.session.commit()
    flash(f'Заказ №{order.id} завершён', 'success')
    return redirect(url_for('waiter_orders'))

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
    app.run(debug=True)





