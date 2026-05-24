from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
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
            flash('Успешный вход!', 'success')
            return redirect(url_for('manager' if user.role == 'admin' else 'index'))
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
@app.route('/manager')
@login_required
def manager():
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    users = User.query.all()
    return render_template('manager.html', users=users)

#Creating a new user
@app.route('/manager/create_user', methods=['POST'])
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
    return redirect(url_for('manager'))

@app.route('/cook/dashboard')
@login_required
def cook_dashboard():
    if current_user.role not in ['cook', 'admin']:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    dishes = MenuItem.query.filter_by(created_by=current_user.id).all()
    return render_template('cook_dashboard.html', dishes=dishes)

@app.route('/manager/pending_menu')
@login_required
def pending_menu():
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    pending_items = MenuItem.query.filter_by(is_approved=False).all()
    return render_template('pending_menu.html', items=pending_items)

# Утверждение блюда менеджером
@app.route('/manager/approve_item/<int:item_id>', methods=['POST'])
@login_required
def approve_item(item_id):
    if current_user.role != 'admin':
        return "Forbidden", 403
    item = MenuItem.query.get_or_404(item_id)
    item.is_approved = True
    item.approved_by = current_user.id
    item.approved_at = db.func.now()
    db.session.commit()
    flash(f'Блюдо "{item.name}" утверждено', 'success')
    return redirect(url_for('pending_menu'))

@app.route('/manager/reject_item/<int:item_id>', methods=['POST'])
@login_required
def reject_item(item_id):
    if current_user.role != 'admin':
        return "Forbidden", 403
    item = MenuItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f'Блюдо "{name}" отклонено и удалено', 'warning')
    return redirect(url_for('pending_menu'))

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





