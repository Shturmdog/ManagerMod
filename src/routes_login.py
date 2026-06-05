from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
from extensions import db
from models import User

login_bp = Blueprint('login', __name__)


@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin.admin'))
            elif user.role == 'cook':
                return redirect(url_for('cook.cook_dashboard'))
            elif user.role == 'waiter':
                return redirect(url_for('waiter.waiter_dashboard'))
            elif user.role == 'manager':
                return redirect(url_for('manager.manager_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Неверное имя или пароль', 'danger')
    return render_template('login.html')


@login_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login.login'))