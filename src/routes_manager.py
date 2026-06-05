from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import MenuItem, Shift, Order, User
from utils import get_shift_statistics
from datetime import datetime

manager_bp = Blueprint('manager', __name__)


@manager_bp.route('/manager/dashboard')
@login_required
def manager_dashboard():
    if current_user.role != 'manager':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    pending_items = MenuItem.query.filter_by(is_approved=False).all()
    active_shift = Shift.query.filter_by(end_time=None).first()
    return render_template('manager_dashboard.html', pending_items=pending_items, active_shift=active_shift)


@manager_bp.route('/manager_dashboard/approve_item/<int:item_id>', methods=['POST'])
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
    return redirect(url_for('manager.manager_dashboard'))


@manager_bp.route('/manager_dashboard/reject_item/<int:item_id>', methods=['POST'])
@login_required
def reject_item(item_id):
    if current_user.role != 'manager':
        return "Forbidden", 403
    item = MenuItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f'Блюдо "{name}" отклонено и удалено', 'warning')
    return redirect(url_for('manager.manager_dashboard'))


@manager_bp.route('/manager_dashboard/shift_stats')
@login_required
def shift_stats():
    if current_user.role != 'manager':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    shifts = Shift.query.filter(Shift.end_time.isnot(None)).order_by(Shift.end_time.desc()).all()
    return render_template('shift_stats.html', shifts=shifts)


@manager_bp.route('/manager_dashboard/open_shift', methods=['POST'])
@login_required
def open_shift():
    if current_user.role != 'manager':
        return "Forbidden", 403
    active_shift = Shift.query.filter_by(end_time=None).first()
    if active_shift:
        flash('Смена уже открыта', 'warning')
    else:
        new_shift = Shift(start_time=datetime.now())
        db.session.add(new_shift)
        db.session.commit()
        flash('Новая смена открыта', 'success')
    return redirect(url_for('manager.manager_dashboard'))


@manager_bp.route('/manager_dashboard/close_shift', methods=['POST'])
@login_required
def close_shift():
    if current_user.role != 'manager':
        return "Forbidden", 403

    active_shift = Shift.query.filter_by(end_time=None).first()
    if not active_shift:
        active_shift = Shift(start_time=datetime.now())
        db.session.add(active_shift)
        db.session.commit()

    total_revenue, best_dish, best_waiter = get_shift_statistics()

    active_shift.end_time = datetime.now()
    active_shift.closed_by = current_user.id
    active_shift.total_revenue = total_revenue
    active_shift.best_dish = best_dish
    active_shift.best_waiter = best_waiter
    if best_waiter:
        best_user = User.query.filter_by(username=best_waiter).first()
        if best_user:
            active_shift.best_waiter_id = best_user.id

    db.session.commit()

    Order.query.filter_by(status='completed').delete()
    db.session.commit()

    flash(f'Смена закрыта. Выручка: {total_revenue} руб., лучшее блюдо: {best_dish}, лучший официант: {best_waiter}', 'success')
    return redirect(url_for('manager.manager_dashboard'))