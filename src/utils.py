from models import Order, User


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