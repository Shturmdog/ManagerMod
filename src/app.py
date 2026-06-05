from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import create_app, db, login_manager
from models import User
import os

app = create_app()

# Import and register blueprints
from routes_login import login_bp
from routes_admin import admin_bp
from routes_manager import manager_bp
from routes_cook import cook_bp
from routes_waiter import waiter_bp

app.register_blueprint(login_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manager_bp)
app.register_blueprint(cook_bp)
app.register_blueprint(waiter_bp)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Create tables and add a test admin
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()


@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html', user=current_user)
    else:
        return redirect(url_for('login.login'))


@app.route('/home')
@login_required
def home():
    return render_template('home.html', user=current_user)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)