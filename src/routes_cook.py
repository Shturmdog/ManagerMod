from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import MenuItem, Order, Shift

cook_bp = Blueprint('cook', __name__)


@cook_bp.route('/cook/dashboard')
@login_required
def cook_dashboard():
    if current_user.role not in ['cook', 'admin']:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    dishes = MenuItem.query.filter_by(created_by=current_user.id).all()
    waiting_orders = Order.query.filter_by(status='waiting').order_by(Order.created_at.asc()).all()
    cooking_orders = Order.query.filter_by(status='cooking').order_by(Order.created_at.asc()).all()
    ready_orders = Order.query.filter_by(status='ready').order_by(Order.updated_at.desc()).all()
    active_shift = Shift.query.filter_by(end_time=None).first()

    return render_template('cook_dashboard.html',
                           dishes=dishes,
                           waiting_orders=waiting_orders,
                           cooking_orders=cooking_orders,
                           ready_orders=ready_orders,
                           active_shift=active_shift)


@cook_bp.route('/cook/create_menu', methods=['GET', 'POST'])
@login_required
def create_menu():
    if current_user.role not in 'cook':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        category = request.form.get('category', 'main')

        if not name or not price:
            flash('Название и цена обязательны', 'danger')
            return redirect(url_for('cook.create_menu'))

        try:
            price = float(price)
        except ValueError:
            flash('Цена должна быть числом', 'danger')
            return redirect(url_for('cook.create_menu'))

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
        return redirect(url_for('cook.cook_dashboard'))

    return render_template('create_menu.html')


@cook_bp.route('/cook/start_cooking/<int:order_id>', methods=['POST'])
@login_required
def start_cooking(order_id):
    if current_user.role not in ['cook', 'admin']:
        return "Forbidden", 403
    active_shift = Shift.query.filter_by(end_time=None).first()
    if not active_shift:
        flash('Смена закрыта. Нельзя начать приготовление.', 'danger')
        return redirect(url_for('cook.cook_dashboard'))
    order = Order.query.get_or_404(order_id)
    if order.status == 'waiting':
        order.status = 'cooking'
        db.session.commit()
        flash(f'Заказ №{order.id} начат приготовление', 'info')
    else:
        flash('Невозможно начать готовку', 'warning')
    return redirect(url_for('cook.cook_dashboard'))


@cook_bp.route('/cook/mark_ready/<int:order_id>', methods=['POST'])
@login_required
def mark_ready(order_id):
    if current_user.role not in ['cook', 'admin']:
        return "Forbidden", 403
    active_shift = Shift.query.filter_by(end_time=None).first()
    if not active_shift:
        flash('Смена закрыта. Нельзя отметить готовность.', 'danger')
        return redirect(url_for('cook.cook_dashboard'))
    order = Order.query.get_or_404(order_id)
    if order.status in ['waiting', 'cooking']:
        order.status = 'ready'
        db.session.commit()
        flash(f'Заказ №{order.id} готов к выдаче', 'success')
    else:
        flash('Некорректный статус', 'warning')
    return redirect(url_for('cook.cook_dashboard'))


@cook_bp.route('/cook/toggle_availability/<int:item_id>', methods=['POST'])
@login_required
def toggle_availability(item_id):
    if current_user.role not in 'cook':
        return "Forbidden", 403
    item = MenuItem.query.get_or_404(item_id)

    item.is_available = not item.is_available
    db.session.commit()

    status = "Доступно" if item.is_available else "Недоступно"
    flash(f'Блюдо "{item.name}" теперь {status}', 'success')
    return redirect(url_for('cook.cook_dashboard'))