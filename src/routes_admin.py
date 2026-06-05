from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import User

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    users = User.query.all()
    return render_template('admin.html', users=users)


@admin_bp.route('/admin/create_user', methods=['POST'])
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
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return "Forbidden", 403

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Вы не можете удалять самого себя", 'danger')
        return redirect(url_for('admin.admin'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь "{username}" удалён', 'success')
    return redirect(url_for('admin.admin'))