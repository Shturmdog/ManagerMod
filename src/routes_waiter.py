from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import MenuItem, Order, OrderItem, Shift

waiter_bp = Blueprint('waiter', __name__)


@waiter_bp.route('/waiter/dashboard')
@login_required
def waiter_dashboard():
    if current_user.role != 'waiter':
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))
    menu_items = MenuItem.query.filter_by(is_approved=True, is_available=True).all()
    active_shift = Shift.query.filter_by(end_time=None).first()
    return render_template('waiter_dashboard.html', menu_items=menu_items, active_shift=active_shift)


@waiter_bp.route('/waiter/create_order', methods=['POST'])
@login_required
def create_order():
    if current_user.role != 'waiter':
        return 'Forbidden', 403
    active_shift = Shift.query.filter_by(end_time=None).first()
    if not active_shift:
        flash('Смена закрыта. Нельзя создать заказ.', 'danger')
        return redirect(url_for('waiter.waiter_dashboard'))

    table_number = request.form.get('table_number')
    if not table_number:
        flash('Не указан номер столика', 'danger')
        return redirect(url_for('waiter.waiter_dashboard'))

    items = {}
    for key in request.form:
        if key.startswith('qty_'):
            menu_item_id = int(key.split('_')[1])
            qty = int(request.form[key])
            if qty > 0:
                items[menu_item_id] = qty

    if not items:
        flash('Не выбрано ни одно блюдо', 'danger')
        return redirect(url_for('waiter.waiter_dashboard'))

    for menu_item_id, quantity in items.items():
        menu_item = MenuItem.query.get(menu_item_id)
        if not menu_item or not menu_item.is_available or not menu_item.is_approved:
            flash(f'Блюдо {menu_item.name if menu_item else "?"} больше недоступно', 'danger')
            db.session.rollback()
            return redirect(url_for('waiter.waiter_dashboard'))

    order = Order(waiter_id=current_user.id, table_number=int(table_number), status='waiting')
    db.session.add(order)
    db.session.commit()

    for menu_item_id, quantity in items.items():
        order_item = OrderItem(order_id=order.id, menu_item_id=menu_item_id, quantity=quantity)
        db.session.add(order_item)

    db.session.commit()
    flash(f'Заказ №{order.id} создан для стола {table_number} и отправлен повару', 'success')
    return redirect(url_for('waiter.waiter_dashboard'))


@waiter_bp.route('/waiter/orders')
@login_required
def waiter_orders():
    if current_user.role != 'waiter':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    active_orders = Order.query.filter(Order.waiter_id == current_user.id, Order.status != 'completed').order_by(Order.created_at.desc()).all()
    completed_orders = Order.query.filter(Order.waiter_id == current_user.id, Order.status == 'completed').order_by(Order.created_at.desc()).limit(20).all()
    return render_template('waiter_orders.html', active_orders=active_orders, completed_orders=completed_orders)


@waiter_bp.route('/waiter/complete_order/<int:order_id>', methods=['POST'])
@login_required
def complete_order(order_id):
    if current_user.role != 'waiter':
        return "Forbidden", 403
    order = Order.query.get_or_404(order_id)
    if order.waiter_id != current_user.id:
        flash('Это не ваш заказ', 'danger')
        return redirect(url_for('waiter.waiter_orders'))
    if order.status != 'ready':
        flash('Заказ ещё не готов', 'warning')
        return redirect(url_for('waiter.waiter_orders'))
    order.status = 'completed'
    db.session.commit()
    flash(f'Заказ №{order.id} завершён', 'success')
    return redirect(url_for('waiter.waiter_orders'))