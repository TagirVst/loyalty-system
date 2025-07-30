import os
from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
from api.config import settings
import secrets
import httpx

app = FastAPI(title="Loyalty Admin Panel", docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

security = HTTPBasic()

def verify_login(credentials: HTTPBasicCredentials):
    correct = secrets.compare_digest(credentials.username, settings.ADMIN_LOGIN) and secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD)
    if not correct:
        return False
    return True

def check_auth(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse("/", status_code=302)
    return None

@app.get("/", response_class=HTMLResponse)
def login_form():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Админ-панель - Система лояльности</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .form-container { background: white; padding: 30px; border-radius: 8px; max-width: 400px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { width: 100%; background: #007bff; color: white; padding: 12px; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; }
            button:hover { background: #0056b3; }
            h2 { color: #333; text-align: center; }
        </style>
    </head>
    <body>
        <div class="form-container">
            <h2>Вход в админ-панель</h2>
            <form method="post" action="/login">
                <input name="username" placeholder="Логин" required>
                <input name="password" type="password" placeholder="Пароль" required>
                <button type="submit">Войти</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if verify_login(HTTPBasicCredentials(username=username, password=password)):
        request.session["admin"] = True
        return RedirectResponse("/dashboard", status_code=302)
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head><title>Ошибка входа</title><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5;">
        <div style="background: white; padding: 30px; border-radius: 8px; max-width: 400px; margin: 0 auto;">
            <h2 style="color: #dc3545;">Неверный логин или пароль</h2>
            <a href="/" style="color: #007bff; text-decoration: none;">← Назад</a>
        </div>
    </body>
    </html>
    """)

def get_base_html(title, content):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title} - Админ-панель</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }}
            .header {{ background: #007bff; color: white; padding: 15px 20px; }}
            .nav {{ background: #0056b3; padding: 10px 20px; }}
            .nav a {{ color: white; text-decoration: none; margin-right: 20px; padding: 8px 12px; border-radius: 4px; }}
            .nav a:hover {{ background: rgba(255,255,255,0.1); }}
            .content {{ padding: 20px; }}
            .card {{ background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 20px; }}
            .stat-card {{ flex: 1; background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Система лояльности - Админ-панель</h1>
        </div>
        <div class="nav">
            <a href="/dashboard">Главная</a>
            <a href="/users">Пользователи</a>
            <a href="/orders">Заказы</a>
            <a href="/gifts">Подарки</a>
            <a href="/feedbacks">Отзывы</a>
            <a href="/ideas">Идеи</a>
            <a href="/analytics">Аналитика</a>
            <a href="/logout">Выйти</a>
        </div>
        <div class="content">
            {content}
        </div>
    </body>
    </html>
    """

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    auth_check = check_auth(request)
    if auth_check:
        return auth_check
    
    async with httpx.AsyncClient() as client:
        try:
            analytics = await client.get("http://api:8000/analytics/summary")
            stats = analytics.json() if analytics.status_code == 200 else {}
        except:
            stats = {}
    
    stats_html = f"""
    <div class="stats">
        <div class="stat-card">
            <div class="stat-number">{stats.get('total_orders', 0)}</div>
            <div>Всего заказов</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{stats.get('total_gifts', 0)}</div>
            <div>Подарков выдано</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{stats.get('total_drinks', 0)}</div>
            <div>Напитков продано</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{stats.get('total_sandwiches', 0)}</div>
            <div>Сэндвичей продано</div>
        </div>
    </div>
    <div class="card">
        <h3>Добро пожаловать в админ-панель!</h3>
        <p>Здесь вы можете управлять системой лояльности:</p>
        <ul>
            <li><strong>Пользователи</strong> - просмотр всех зарегистрированных клиентов</li>
            <li><strong>Заказы</strong> - история всех заказов</li>
            <li><strong>Подарки</strong> - выданные подарки и акции</li>
            <li><strong>Отзывы</strong> - отзывы клиентов о сервисе</li>
            <li><strong>Идеи</strong> - предложения от клиентов</li>
            <li><strong>Аналитика</strong> - статистика и отчеты</li>
        </ul>
    </div>
    """
    
    return get_base_html("Главная", stats_html)

@app.get("/users", response_class=HTMLResponse)
async def users(request: Request):
    auth_check = check_auth(request)
    if auth_check:
        return auth_check
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://api:8000/users/")
            users_data = r.json() if r.status_code == 200 else []
        except:
            users_data = []
    
    users_table = """
    <div class="card">
        <h3>Пользователи системы</h3>
        <table>
            <tr>
                <th>ID</th>
                <th>Имя</th>
                <th>Телефон</th>
                <th>Уровень</th>
                <th>Баллы</th>
                <th>Напитков</th>
                <th>Сэндвичей</th>
                <th>Статус</th>
            </tr>
    """
    
    for user in users_data:
        status = "Активен" if user.get('is_active') else "Неактивен"
        users_table += f"""
            <tr>
                <td>{user.get('id', '')}</td>
                <td>{user.get('first_name', '')} {user.get('last_name', '')}</td>
                <td>{user.get('phone', '')}</td>
                <td>{user.get('loyalty_status', '')}</td>
                <td>{user.get('points', 0)}</td>
                <td>{user.get('drinks_count', 0)}</td>
                <td>{user.get('sandwiches_count', 0)}</td>
                <td>{status}</td>
            </tr>
        """
    
    users_table += "</table></div>"
    return get_base_html("Пользователи", users_table)

@app.get("/orders", response_class=HTMLResponse)
async def orders(request: Request):
    auth_check = check_auth(request)
    if auth_check:
        return auth_check
    
    # Здесь нужно было бы добавить API endpoint для получения всех заказов
    # Пока показываем заглушку
    content = """
    <div class="card">
        <h3>Заказы</h3>
        <p>Для отображения заказов необходимо добавить соответствующий API endpoint.</p>
        <p>Пример: GET /api/orders/ - получить все заказы</p>
    </div>
    """
    return get_base_html("Заказы", content)

@app.get("/gifts", response_class=HTMLResponse)
async def gifts(request: Request):
    auth_check = check_auth(request)
    if auth_check:
        return auth_check
    
    content = """
    <div class="card">
        <h3>Подарки</h3>
        <p>Для отображения подарков необходимо добавить соответствующий API endpoint.</p>
        <p>Пример: GET /api/gifts/ - получить все подарки</p>
    </div>
    """
    return get_base_html("Подарки", content)

@app.get("/feedbacks", response_class=HTMLResponse)
async def feedbacks(request: Request):
    auth_check = check_auth(request)
    if auth_check:
        return auth_check
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://api:8000/feedback/")
            feedbacks_data = r.json() if r.status_code == 200 else []
        except:
            feedbacks_data = []
    
    feedback_table = """
    <div class="card">
        <h3>Отзывы клиентов</h3>
        <table>
            <tr>
                <th>ID</th>
                <th>Пользователь</th>
                <th>Оценка</th>
                <th>Текст</th>
                <th>Дата</th>
            </tr>
    """
    
    for feedback in feedbacks_data:
        feedback_table += f"""
            <tr>
                <td>{feedback.get('id', '')}</td>
                <td>ID: {feedback.get('user_id', '')}</td>
                <td>{feedback.get('score', '')}/10</td>
                <td>{feedback.get('text', '')[:100]}{'...' if len(str(feedback.get('text', ''))) > 100 else ''}</td>
                <td>{feedback.get('created_at', '')}</td>
            </tr>
        """
    
    feedback_table += "</table></div>"
    return get_base_html("Отзывы", feedback_table)

@app.get("/ideas", response_class=HTMLResponse)
async def ideas(request: Request):
    auth_check = check_auth(request)
    if auth_check:
        return auth_check
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://api:8000/feedback/ideas")
            ideas_data = r.json() if r.status_code == 200 else []
        except:
            ideas_data = []
    
    ideas_table = """
    <div class="card">
        <h3>Идеи от клиентов</h3>
        <table>
            <tr>
                <th>ID</th>
                <th>Пользователь</th>
                <th>Идея</th>
                <th>Дата</th>
            </tr>
    """
    
    for idea in ideas_data:
        ideas_table += f"""
            <tr>
                <td>{idea.get('id', '')}</td>
                <td>ID: {idea.get('user_id', '')}</td>
                <td>{idea.get('text', '')[:200]}{'...' if len(str(idea.get('text', ''))) > 200 else ''}</td>
                <td>{idea.get('created_at', '')}</td>
            </tr>
        """
    
    ideas_table += "</table></div>"
    return get_base_html("Идеи", ideas_table)

@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    auth_check = check_auth(request)
    if auth_check:
        return auth_check
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://api:8000/analytics/summary")
            analytics_data = r.json() if r.status_code == 200 else {}
        except:
            analytics_data = {}
    
    analytics_content = f"""
    <div class="card">
        <h3>Аналитика системы</h3>
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{analytics_data.get('total_orders', 0)}</div>
                <div>Всего заказов</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{analytics_data.get('total_gifts', 0)}</div>
                <div>Подарков выдано</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{analytics_data.get('total_drinks', 0)}</div>
                <div>Напитков продано</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{analytics_data.get('total_sandwiches', 0)}</div>
                <div>Сэндвичей продано</div>
            </div>
        </div>
    </div>
    """
    
    return get_base_html("Аналитика", analytics_content)

@app.get("/logout")
def logout(request: Request):
    request.session.pop("admin", None)
    return RedirectResponse("/", status_code=302)
