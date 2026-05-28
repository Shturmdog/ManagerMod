

## 1. Архитектура системы

```
┌─────────────────────────────────────────────────────────────────┐
│                    RESTAURANT MANAGEMENT SYSTEM                  │
│                         (Flask + SQLite)                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │         SQLite Database         │
              │  (users, menu, orders, shifts)  │
              └─────────────────────────────────┘
                               │
        ┌──────────┬──────────┼──────────┬──────────┐
        ▼          ▼          ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │ ADMIN  │ │MANAGER │ │ COOK   │ │WAITER  │
   │ Module │ │ Module │ │ Module │ │ Module │
   └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘
        │          │          │          │
        ▼          ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │ users  │ │menu_   │ │ orders │ │order_  │
   │ table  │ │items   │ │ table  │ │items   │
   └────────┘ │ table  │ └────────┘ │ table  │
              └────────┘            └────────┘
              ┌────────┐
              │ shifts │
              │ table  │
              └────────┘
```

---

## 2. Модули и их функции

### 2.1 Модуль Администратора (Admin)
**Маршруты:** `/admin`, `/admin/create_user`, `/admin/delete_user/<id>`

| Функция | Описание | SQL-эквивалент |
|---------|----------|----------------|
| Создание пользователя | Добавление нового сотрудника с ролью | `INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)` |
| Удаление пользователя | Удаление учётной записи | `DELETE FROM users WHERE id = ?` |
| Просмотр списка | Отображение всех пользователей | `SELECT * FROM users` |

---

### 2.2 Модуль Менеджера (Manager)
**Маршруты:** `/manager/dashboard`, `/manager_dashboard/*`

| Функция | Описание | SQL-эквивалент |
|---------|----------|----------------|
| Утверждение блюда | Одобрение блюда от повара | `UPDATE menu_items SET is_approved=1, approved_by=? WHERE id=?` |
| Отклонение блюда | Удаление неподходящего блюда | `DELETE FROM menu_items WHERE id = ?` |
| Открытие смены | Создание новой рабочей смены | `INSERT INTO shifts (start_time) VALUES (datetime('now'))` |
| Закрытие смены | Фиксация статистики смены | `UPDATE shifts SET end_time=?, total_revenue=?, best_dish=?, best_waiter=? WHERE id=?` |
| Статистика смен | Выручка, лучшее блюдо, официант | `SELECT SUM(price*qty), MAX(dish_count), MAX(waiter_revenue) FROM orders...` |

---

### 2.3 Модуль Повара (Cook)
**Маршруты:** `/cook/dashboard`, `/cook/*`

| Функция | Описание | SQL-эквивалент |
|---------|----------|----------------|
| Просмотр заказов | Фильтрация по статусам | `SELECT * FROM orders WHERE status IN ('waiting','cooking','ready') ORDER BY created_at` |
| Начать готовку | Смена статуса на "cooking" | `UPDATE orders SET status='cooking' WHERE id=?` |
| Отметить готовым | Смена статуса на "ready" | `UPDATE orders SET status='ready', updated_at=datetime('now') WHERE id=?` |
| Создать блюдо | Добавление на утверждение | `INSERT INTO menu_items (name, price, category, created_by, is_approved) VALUES (?, ?, ?, ?, 0)` |
| Переключить доступность | Вкл/выкл блюда | `UPDATE menu_items SET is_available = NOT is_available WHERE id=?` |

---

### 2.4 Модуль Официанта (Waiter)
**Цвет:** 🔵 Синий  
**Маршруты:** `/waiter/dashboard`, `/waiter/*`

| Функция | Описание | SQL-эквивалент |
|---------|----------|----------------|
| Создание заказа | Выбор столика и блюд | `INSERT INTO orders (waiter_id, table_number, status) VALUES (?, ?, 'waiting')` |
| Добавление позиций | Связь заказа с блюдами | `INSERT INTO order_items (order_id, menu_item_id, quantity) VALUES (?, ?, ?)` |
| Просмотр заказов | Активные и завершённые | `SELECT * FROM orders WHERE waiter_id=? AND status!='completed'` |
| Завершение заказа | Кнопка "Забрал" | `UPDATE orders SET status='completed' WHERE id=?` |



## 4. Потоки данных (Data Flow)

### 4.1 Жизненный цикл заказа
```
Официант создаёт ──► Повар видит ──► Повар начинает ──► Повар отмечает ──► Официант забирает
    заказ              "waiting"        "cooking"          "ready"            "completed"
    
[POST /waiter/      [SELECT *        [UPDATE orders    [UPDATE orders     [UPDATE orders
 create_order]       WHERE status=     SET status=        SET status=         SET status=
                     'waiting']        'cooking']         'ready']            'completed']
```

### 4.2 Жизненный цикл блюда
```
Повар создаёт ──► Менеджер утверждает ──► Блюдо доступно ──► Повар может вкл/выкл
   (pending)          (approved)            для заказов         доступность
   
[INSERT menu_items   [UPDATE menu_items    [SELECT * FROM      [UPDATE menu_items
 is_approved=0]      SET is_approved=1]     menu_items WHERE     SET is_available=
                                             is_approved=1]       NOT is_available]
```

### 4.3 Жизненный цикл смены
```
Менеджер открывает ──► Идут заказы ──► Менеджер закрывает ──► Автоматический расчёт
   смену                и готовка        смену                 статистики
   
[INSERT shifts        [orders создаются   [UPDATE shifts        [SELECT SUM() FROM
 start_time=now]      поварами готовят]    SET end_time=now,     orders + агрегация
                                            total_revenue=?,     по блюдам и официантам
                                            best_dish=?,
                                            best_waiter=?]
```

---

## 5. Сравнение с аналогами

| Параметр | Iiko | R-Keeper | Tillypad | Наша система |
|----------|------|----------|----------|--------------|
| **Стоимость** | Платная | Платная | Платная | **Бесплатная (Open Source)** |
| **Установка** | Локальный сервер | Локальный сервер | Локальный сервер | **Веб-доступ с любого устройства** |
| **Сложность** | Высокая | Высокая | Средняя | **Низкая (минимум кнопок)** |
| **Ролевая модель** | Гибкая, сложная | Гибкая, сложная | Стандартная | **Адаптирована под малое заведение** |
| **База данных** | PostgreSQL | MSSQL | PostgreSQL | **SQLite (встроенная)** |
| **Утверждение блюд** | Нет | Нет | Нет | **Есть (повар → менеджер)** |
| **Смены со статистикой** | Есть | Есть | Есть | **Есть + авторасчёт** |

---

## 6. Примеры SQL-запросов (соответствие коду)

### 6.1 Получение заказов повара с позициями
```sql
-- Эквивалент Order.query.filter_by(status='waiting').all()
SELECT o.id, o.table_number, o.status, o.created_at,
       u.username as waiter_name
FROM orders o
JOIN users u ON o.waiter_id = u.id
WHERE o.status = 'waiting'
ORDER BY o.created_at ASC;
```

### 6.2 Расчёт выручки смены
```sql
-- Эквивалент get_shift_statistics()
SELECT 
    SUM(mi.price * oi.quantity) as total_revenue
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN menu_items mi ON oi.menu_item_id = mi.id
WHERE o.status = 'completed';
```

### 6.3 Лучшее блюдо смены
```sql
-- Эквивалент dish_count в Python
SELECT 
    mi.name,
    SUM(oi.quantity) as total_ordered
FROM order_items oi
JOIN menu_items mi ON oi.menu_item_id = mi.id
JOIN orders o ON oi.order_id = o.id
WHERE o.status = 'completed'
GROUP BY mi.name
ORDER BY total_ordered DESC
LIMIT 1;
```

### 6.4 Лучший официант смены
```sql
-- Эквивалент waiter_revenue в Python
SELECT 
    u.username,
    SUM(mi.price * oi.quantity) as revenue
FROM orders o
JOIN users u ON o.waiter_id = u.id
JOIN order_items oi ON o.id = oi.order_id
JOIN menu_items mi ON oi.menu_item_id = mi.id
WHERE o.status = 'completed'
GROUP BY u.username
ORDER BY revenue DESC
LIMIT 1;
```


## 8. Правила

| Правило | Реализация в коде |
|---------|-------------------|
| Только менеджер может открыть/закрыть смену | `@login_required` + `if current_user.role != 'manager'` |
| Блюдо должно быть утверждено перед заказом | `MenuItem.query.filter_by(is_approved=True, is_available=True)` |
| Заказ можно создать только при открытой смене | `Shift.query.filter_by(end_time=None).first()` |
| Повар может готовить только при открытой смене | Проверка active_shift в `start_cooking`, `mark_ready` |
| Официант завершает только свои заказы | `if order.waiter_id != current_user.id` |
| Админ не может удалить сам себя | `if user.id == current_user.id` |
| Пароли хранятся в хешированном виде | `werkzeug.security.generate_password_hash` |

---

## 9. Описание целевой аудитории и решаемые задачи

**Целевая аудитория** — сотрудники ресторана (администратор, менеджер, повар, официант) и владелец заведения.

### Типовые задачи, решаемые с помощью базы данных:

| Роль | Задачи |
|------|--------|
| **Администратор** | • Управление учётными записями сотрудников (создание, удаление, назначение ролей)  <br>• Просмотр списка всех пользователей |
| **Менеджер** | • Утверждение или отклонение новых блюд, предложенных поварами  <br>• Открытие и закрытие смены  <br>• Просмотр статистики смены (выручка, лучшее блюдо, лучший официант)  <br>• История закрытых смен |
| **Повар** | • Просмотр заказов (ожидающие, в процессе, готовые)  <br>• Изменение статуса заказа (начать готовить, отметить готовым)  <br>• Создание новых блюд (название, цена, категория)  <br>• Включение/отключение доступности своих блюд |
| **Официант** | • Создание заказа (выбор столика, выбор блюд, количество)  <br>• Просмотр своих активных заказов и их статусов  <br>• Завершение заказа (кнопка «Забрал») |

**База данных обеспечивает** хранение пользователей, блюд, заказов, позиций заказов и смен, а также поддержку бизнес-правил (утверждение блюд, открытые/закрытые смены, автоматический расчёт выручки).

---

| Родитель     | → | Дочерняя таблица            | Смысл                           |
| ------------ | - | --------------------------- | ------------------------------- |
| `users`      | → | `menu_items` (created\_by)  | Повар создал много блюд         |
| `users`      | → | `menu_items` (approved\_by) | Менеджер утвердил много блюд    |
| `users`      | → | `orders` (waiter\_id)       | Официант обслужил много заказов |
| `users`      | → | `shifts` (closed\_by)       | Менеджер закрыл много смен      |
| `categories` | → | `menu_items`                | Категория содержит много блюд   |
| `tables`     | → | `orders`                    | За столом было много заказов    |
| `orders`     | → | `order_items`               | Заказ содержит много позиций    |
| `menu_items` | → | `order_items`               | Блюдо заказывали много раз      |


---

## 10. Существующие аналоги на рынке ПО

1. **Iiko**
2. **R_Keeper**
3. **Tillypad**

### Отличия разрабатываемой системы:

- **Простота и низкий порог входа** — не требует установки сложного ПО
- **Ролевая модель** — адаптирована под небольшое заведение
- **Веб-доступ** — с любого устройства
- **Бесплатна** — использует Open Source

