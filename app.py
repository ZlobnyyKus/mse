from __future__ import annotations

import os
import sqlite3
from functools import wraps
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE = INSTANCE_DIR / "site.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-key-for-production"
app.config["DATABASE"] = str(DATABASE)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        g.db = db
    return g.db


@app.teardown_appcontext
def close_db(exception: Exception | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return get_db().execute(sql, params).fetchone()


def execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    db = get_db()
    db.execute(sql, params)
    db.commit()


def init_db() -> None:
    INSTANCE_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(DATABASE) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                content TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                content TEXT NOT NULL,
                image TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                summary TEXT NOT NULL,
                content TEXT NOT NULL,
                image TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Новое',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )

        user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            db.executemany(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                [
                    ("admin", generate_password_hash("admin123"), "Администратор сайта", "admin"),
                    ("user", generate_password_hash("user123"), "Тестовый пользователь", "user"),
                ],
            )

        page_count = db.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        if page_count == 0:
            pages = [
                (
                    "about",
                    "Об учреждении",
                    "ФКУ «Главное бюро медико-социальной экспертизы по Нижегородской области» осуществляет организацию и проведение медико-социальной экспертизы граждан. Информационный сайт предназначен для размещения сведений о направлениях работы учреждения, порядке обращения граждан, услугах, документах и контактной информации. Основная задача сайта — сделать получение справочной информации более удобным и понятным для посетителей.",
                ),
                (
                    "services",
                    "Услуги МСЭ",
                    "Раздел содержит сведения об основных направлениях медико-социальной экспертизы: установление инвалидности, разработка индивидуальной программы реабилитации или абилитации, переосвидетельствование, консультирование по вопросам прохождения экспертизы и подготовка необходимых документов.",
                ),
                (
                    "citizens",
                    "Гражданам",
                    "Раздел предназначен для граждан, которым необходимо пройти медико-социальную экспертизу. Здесь размещается порядок обращения, перечень документов, общие рекомендации по подготовке заявления и ответы на типовые вопросы.",
                ),
                (
                    "documents",
                    "Документы",
                    "В разделе собраны справочные материалы о документах, которые могут потребоваться при обращении в учреждение. Материалы сгруппированы по темам и помогают пользователю заранее подготовиться к обращению.",
                ),
                (
                    "contacts",
                    "Контакты",
                    "На странице представлены контактные данные учреждения, режим работы и форма обратной связи. Пользователь может отправить сообщение через сайт, после чего оно становится доступным администратору в панели управления.",
                ),
            ]
            db.executemany("INSERT INTO pages (slug, title, content) VALUES (?, ?, ?)", pages)

        news_count = db.execute("SELECT COUNT(*) FROM news").fetchone()[0]
        if news_count == 0:
            news = [
                (
                    "Обновлен порядок записи на консультацию",
                    "На сайте размещена информация о порядке предварительной записи и подготовке документов.",
                    "Учреждение информирует граждан о возможности заранее ознакомиться с перечнем документов и общими правилами обращения. Это помогает сократить количество повторных обращений и уменьшить нагрузку на сотрудников, работающих с гражданами.",
                    "",
                ),
                (
                    "Добавлен раздел с полезными материалами",
                    "В новом разделе опубликованы справочные статьи по вопросам прохождения МСЭ.",
                    "Полезные материалы помогают гражданам разобраться в процедуре прохождения экспертизы, сроках, документах и порядке получения консультации. Раздел будет регулярно пополняться новыми публикациями.",
                    "",
                ),
                (
                    "Разработана версия сайта для слабовидящих",
                    "Пользователи могут переключить интерфейс в режим повышенной доступности.",
                    "Версия для слабовидящих предусматривает крупный шрифт, высокий контраст, упрощенную визуальную структуру и сохранение основной навигации. Переключатель расположен в верхней части сайта.",
                    "",
                ),
                (
                    "Обновлена контактная информация",
                    "В разделе контактов уточнены способы связи и режим приема обращений.",
                    "Контактная страница содержит основные каналы связи, адрес учреждения и форму обратной связи. Сообщения, отправленные через форму, сохраняются в базе данных сайта.",
                    "",
                ),
                (
                    "Запущен поиск по сайту",
                    "Поиск помогает быстро находить новости, статьи и справочные страницы.",
                    "Поисковый механизм выполняет поиск по заголовкам и текстам материалов. Это особенно полезно для пользователей, которым нужно быстро найти информацию о документах, услугах или порядке обращения.",
                    "",
                ),
            ]
            db.executemany("INSERT INTO news (title, summary, content, image) VALUES (?, ?, ?, ?)", news)

        article_count = db.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        if article_count == 0:
            articles = []
            services_articles = [
                ("Первичное освидетельствование", "Как подготовиться к первичному прохождению медико-социальной экспертизы."),
                ("Повторное освидетельствование", "Когда требуется повторное обращение и какие сведения нужно подготовить."),
                ("Индивидуальная программа реабилитации", "Назначение ИПРА и роль программы в дальнейшем сопровождении гражданина."),
                ("Консультирование граждан", "Какие вопросы можно уточнить до подачи заявления."),
                ("Направление на экспертизу", "Кто оформляет направление и какие сведения в нем отражаются."),
            ]
            citizens_articles = [
                ("Порядок обращения", "Основные этапы обращения гражданина в учреждение."),
                ("Подготовка заявления", "Какие сведения важно проверить перед подачей заявления."),
                ("Сроки рассмотрения", "Общие сведения о сроках и этапах рассмотрения материалов."),
                ("Частые вопросы", "Краткие ответы на типовые вопросы посетителей сайта."),
                ("Получение консультации", "Как пользователь может задать вопрос через форму обратной связи."),
            ]
            document_articles = [
                ("Документ, удостоверяющий личность", "Зачем нужен основной документ гражданина при обращении."),
                ("Медицинские документы", "Какие медицинские сведения помогают рассмотреть обращение."),
                ("Справки и выписки", "Как использовать дополнительные справочные материалы."),
                ("Документы представителя", "Что требуется при обращении через законного представителя."),
                ("Проверка комплекта документов", "Как заранее проверить полноту подготовленного комплекта."),
            ]
            for title, summary in services_articles:
                articles.append((title, "Услуги МСЭ", summary, f"{summary} Материал подготовлен для информационного сопровождения посетителей сайта. Он помогает понять назначение услуги, порядок получения информации и связь услуги с общей процедурой медико-социальной экспертизы.", ""))
            for title, summary in citizens_articles:
                articles.append((title, "Гражданам", summary, f"{summary} Статья ориентирована на граждан, которым необходимо получить понятную справочную информацию без обращения к сложным формулировкам. Материал дополняет основные разделы сайта и помогает быстрее найти нужный порядок действий.", ""))
            for title, summary in document_articles:
                articles.append((title, "Документы", summary, f"{summary} Публикация объясняет, почему соответствующий документ может быть важен при обращении, как он используется в информационном процессе и какие ошибки чаще всего возникают при подготовке комплекта сведений.", ""))
            db.executemany(
                "INSERT INTO articles (title, category, summary, content, image) VALUES (?, ?, ?, ?, ?)",
                articles,
            )


def current_user() -> sqlite3.Row | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return query_one("SELECT * FROM users WHERE id = ?", (user_id,))


@app.context_processor
def inject_common() -> dict[str, Any]:
    return {
        "current_user": current_user(),
        "main_menu": [
            ("Главная", "index"),
            ("Об учреждении", "about"),
            ("Услуги МСЭ", "services"),
            ("Гражданам", "citizens"),
            ("Документы", "documents"),
            ("Новости", "news_list"),
            ("Контакты", "contacts"),
        ],
    }


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if current_user() is None:
            flash("Для доступа к странице необходимо войти в систему.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        user = current_user()
        if user is None or user["role"] != "admin":
            flash("Доступ разрешен только администратору.", "danger")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def breadcrumbs(*items: tuple[str, str | None]) -> list[tuple[str, str | None]]:
    return [("Главная", url_for("index")), *items]


@app.route("/")
def index():
    latest_news = query_all("SELECT * FROM news ORDER BY datetime(created_at) DESC LIMIT 3")
    popular_articles = query_all("SELECT * FROM articles ORDER BY id LIMIT 6")
    return render_template(
        "index.html",
        title="Главная",
        latest_news=latest_news,
        popular_articles=popular_articles,
        breadcrumbs=[("Главная", None)],
    )


@app.route("/about")
def about():
    page = query_one("SELECT * FROM pages WHERE slug = ?", ("about",))
    return render_template("page.html", title="Об учреждении", page=page, breadcrumbs=breadcrumbs(("Об учреждении", None)))


@app.route("/services")
def services():
    page = query_one("SELECT * FROM pages WHERE slug = ?", ("services",))
    articles = query_all("SELECT * FROM articles WHERE category = ? ORDER BY id", ("Услуги МСЭ",))
    return render_template("category_page.html", title="Услуги МСЭ", page=page, articles=articles, breadcrumbs=breadcrumbs(("Услуги МСЭ", None)))


@app.route("/citizens")
def citizens():
    page = query_one("SELECT * FROM pages WHERE slug = ?", ("citizens",))
    articles = query_all("SELECT * FROM articles WHERE category = ? ORDER BY id", ("Гражданам",))
    return render_template("category_page.html", title="Гражданам", page=page, articles=articles, breadcrumbs=breadcrumbs(("Гражданам", None)))


@app.route("/documents")
def documents():
    page = query_one("SELECT * FROM pages WHERE slug = ?", ("documents",))
    articles = query_all("SELECT * FROM articles WHERE category = ? ORDER BY id", ("Документы",))
    return render_template("category_page.html", title="Документы", page=page, articles=articles, breadcrumbs=breadcrumbs(("Документы", None)))


@app.route("/news")
def news_list():
    news_items = query_all("SELECT * FROM news ORDER BY datetime(created_at) DESC")
    return render_template("news.html", title="Новости", news_items=news_items, breadcrumbs=breadcrumbs(("Новости", None)))


@app.route("/news/<int:item_id>")
def news_detail(item_id: int):
    item = query_one("SELECT * FROM news WHERE id = ?", (item_id,))
    if item is None:
        abort(404)
    return render_template("news_detail.html", title=item["title"], item=item, breadcrumbs=breadcrumbs(("Новости", url_for("news_list")), (item["title"], None)))


@app.route("/articles/<int:item_id>")
def article_detail(item_id: int):
    article = query_one("SELECT * FROM articles WHERE id = ?", (item_id,))
    if article is None:
        abort(404)
    category_routes = {
        "Услуги МСЭ": "services",
        "Гражданам": "citizens",
        "Документы": "documents",
    }
    category_endpoint = category_routes.get(article["category"], "index")
    return render_template(
        "article_detail.html",
        title=article["title"],
        article=article,
        breadcrumbs=breadcrumbs((article["category"], url_for(category_endpoint)), (article["title"], None)),
    )


@app.route("/contacts", methods=["GET", "POST"])
def contacts():
    page = query_one("SELECT * FROM pages WHERE slug = ?", ("contacts",))
    user = current_user()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        if not all([name, email, subject, message]):
            flash("Заполните все поля формы обратной связи.", "danger")
        else:
            execute(
                "INSERT INTO messages (user_id, name, email, subject, message) VALUES (?, ?, ?, ?, ?)",
                (user["id"] if user else None, name, email, subject, message),
            )
            flash("Сообщение отправлено. Администратор сможет просмотреть его в панели управления.", "success")
            return redirect(url_for("contacts"))
    return render_template("contacts.html", title="Контакты", page=page, user=user, breadcrumbs=breadcrumbs(("Контакты", None)))


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    page_results: list[sqlite3.Row] = []
    news_results: list[sqlite3.Row] = []
    article_results: list[sqlite3.Row] = []
    if q:
        like = f"%{q}%"
        page_results = query_all("SELECT * FROM pages WHERE title LIKE ? OR content LIKE ?", (like, like))
        news_results = query_all("SELECT * FROM news WHERE title LIKE ? OR summary LIKE ? OR content LIKE ?", (like, like, like))
        article_results = query_all("SELECT * FROM articles WHERE title LIKE ? OR summary LIKE ? OR content LIKE ? OR category LIKE ?", (like, like, like, like))
    return render_template(
        "search.html",
        title="Поиск",
        q=q,
        page_results=page_results,
        news_results=news_results,
        article_results=article_results,
        breadcrumbs=breadcrumbs(("Поиск", None)),
    )


@app.route("/sitemap")
def sitemap():
    articles = query_all("SELECT * FROM articles ORDER BY category, title")
    news_items = query_all("SELECT * FROM news ORDER BY datetime(created_at) DESC")
    return render_template("sitemap.html", title="Карта сайта", articles=articles, news_items=news_items, breadcrumbs=breadcrumbs(("Карта сайта", None)))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        if not username or not full_name or not password:
            flash("Заполните все поля регистрации.", "danger")
        elif len(password) < 6:
            flash("Пароль должен содержать не менее 6 символов.", "danger")
        else:
            try:
                execute(
                    "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, 'user')",
                    (username, generate_password_hash(password), full_name),
                )
                flash("Учетная запись создана. Теперь можно войти на сайт.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Пользователь с таким логином уже существует.", "danger")
    return render_template("register.html", title="Регистрация", breadcrumbs=breadcrumbs(("Регистрация", None)))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query_one("SELECT * FROM users WHERE username = ?", (username,))
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Вход выполнен успешно.", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_index"))
            return redirect(url_for("profile"))
        flash("Неверный логин или пароль.", "danger")
    return render_template("login.html", title="Вход", breadcrumbs=breadcrumbs(("Вход", None)))


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из учетной записи.", "success")
    return redirect(url_for("index"))


@app.route("/profile")
@login_required
def profile():
    user = current_user()
    messages = query_all("SELECT * FROM messages WHERE user_id = ? ORDER BY datetime(created_at) DESC", (user["id"],))
    return render_template("profile.html", title="Личный кабинет", messages=messages, breadcrumbs=breadcrumbs(("Личный кабинет", None)))


@app.route("/admin")
@admin_required
def admin_index():
    counts = {
        "news": query_one("SELECT COUNT(*) AS c FROM news")["c"],
        "articles": query_one("SELECT COUNT(*) AS c FROM articles")["c"],
        "messages": query_one("SELECT COUNT(*) AS c FROM messages")["c"],
        "users": query_one("SELECT COUNT(*) AS c FROM users")["c"],
    }
    return render_template("admin/index.html", title="Панель администратора", counts=counts, breadcrumbs=breadcrumbs(("Панель администратора", None)))


@app.route("/admin/news")
@admin_required
def admin_news():
    items = query_all("SELECT * FROM news ORDER BY datetime(created_at) DESC")
    return render_template("admin/news_list.html", title="Управление новостями", items=items, breadcrumbs=breadcrumbs(("Панель администратора", url_for("admin_index")), ("Новости", None)))


@app.route("/admin/news/create", methods=["GET", "POST"])
@admin_required
def admin_news_create():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        summary = request.form.get("summary", "").strip()
        content = request.form.get("content", "").strip()
        if not title or not summary or not content:
            flash("Заполните заголовок, краткое описание и текст новости.", "danger")
        else:
            execute("INSERT INTO news (title, summary, content, image) VALUES (?, ?, ?, '')", (title, summary, content))
            flash("Новость добавлена.", "success")
            return redirect(url_for("admin_news"))
    return render_template("admin/news_form.html", title="Добавить новость", item=None, breadcrumbs=breadcrumbs(("Панель администратора", url_for("admin_index")), ("Новости", url_for("admin_news")), ("Добавить", None)))


@app.route("/admin/news/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_news_edit(item_id: int):
    item = query_one("SELECT * FROM news WHERE id = ?", (item_id,))
    if item is None:
        abort(404)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        summary = request.form.get("summary", "").strip()
        content = request.form.get("content", "").strip()
        if not title or not summary or not content:
            flash("Заполните заголовок, краткое описание и текст новости.", "danger")
        else:
            execute("UPDATE news SET title = ?, summary = ?, content = ? WHERE id = ?", (title, summary, content, item_id))
            flash("Новость обновлена.", "success")
            return redirect(url_for("admin_news"))
    return render_template("admin/news_form.html", title="Редактировать новость", item=item, breadcrumbs=breadcrumbs(("Панель администратора", url_for("admin_index")), ("Новости", url_for("admin_news")), ("Редактировать", None)))


@app.route("/admin/news/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_news_delete(item_id: int):
    execute("DELETE FROM news WHERE id = ?", (item_id,))
    flash("Новость удалена.", "success")
    return redirect(url_for("admin_news"))


@app.route("/admin/articles")
@admin_required
def admin_articles():
    items = query_all("SELECT * FROM articles ORDER BY category, title")
    return render_template("admin/articles_list.html", title="Управление материалами", items=items, breadcrumbs=breadcrumbs(("Панель администратора", url_for("admin_index")), ("Материалы", None)))


@app.route("/admin/articles/create", methods=["GET", "POST"])
@admin_required
def admin_articles_create():
    categories = ["Услуги МСЭ", "Гражданам", "Документы"]
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        summary = request.form.get("summary", "").strip()
        content = request.form.get("content", "").strip()
        if not title or category not in categories or not summary or not content:
            flash("Заполните все поля материала и выберите корректную категорию.", "danger")
        else:
            execute("INSERT INTO articles (title, category, summary, content, image) VALUES (?, ?, ?, ?, '')", (title, category, summary, content))
            flash("Материал добавлен.", "success")
            return redirect(url_for("admin_articles"))
    return render_template("admin/article_form.html", title="Добавить материал", item=None, categories=categories, breadcrumbs=breadcrumbs(("Панель администратора", url_for("admin_index")), ("Материалы", url_for("admin_articles")), ("Добавить", None)))


@app.route("/admin/articles/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_articles_edit(item_id: int):
    categories = ["Услуги МСЭ", "Гражданам", "Документы"]
    item = query_one("SELECT * FROM articles WHERE id = ?", (item_id,))
    if item is None:
        abort(404)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        summary = request.form.get("summary", "").strip()
        content = request.form.get("content", "").strip()
        if not title or category not in categories or not summary or not content:
            flash("Заполните все поля материала и выберите корректную категорию.", "danger")
        else:
            execute("UPDATE articles SET title = ?, category = ?, summary = ?, content = ? WHERE id = ?", (title, category, summary, content, item_id))
            flash("Материал обновлен.", "success")
            return redirect(url_for("admin_articles"))
    return render_template("admin/article_form.html", title="Редактировать материал", item=item, categories=categories, breadcrumbs=breadcrumbs(("Панель администратора", url_for("admin_index")), ("Материалы", url_for("admin_articles")), ("Редактировать", None)))


@app.route("/admin/articles/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_articles_delete(item_id: int):
    execute("DELETE FROM articles WHERE id = ?", (item_id,))
    flash("Материал удален.", "success")
    return redirect(url_for("admin_articles"))


@app.route("/admin/messages")
@admin_required
def admin_messages():
    items = query_all("SELECT m.*, u.username FROM messages m LEFT JOIN users u ON m.user_id = u.id ORDER BY datetime(m.created_at) DESC")
    return render_template("admin/messages.html", title="Сообщения пользователей", items=items, breadcrumbs=breadcrumbs(("Панель администратора", url_for("admin_index")), ("Сообщения", None)))


@app.route("/admin/messages/<int:item_id>/status", methods=["POST"])
@admin_required
def admin_message_status(item_id: int):
    status = request.form.get("status", "Новое")
    if status not in ["Новое", "В работе", "Закрыто"]:
        status = "Новое"
    execute("UPDATE messages SET status = ? WHERE id = ?", (status, item_id))
    flash("Статус сообщения обновлен.", "success")
    return redirect(url_for("admin_messages"))


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")
        if not username or not full_name or not password or role not in ["admin", "user"]:
            flash("Заполните все поля пользователя.", "danger")
        else:
            try:
                execute(
                    "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                    (username, generate_password_hash(password), full_name, role),
                )
                flash("Пользователь создан.", "success")
                return redirect(url_for("admin_users"))
            except sqlite3.IntegrityError:
                flash("Пользователь с таким логином уже существует.", "danger")
    users = query_all("SELECT * FROM users ORDER BY role, username")
    return render_template("admin/users.html", title="Пользователи", users=users, breadcrumbs=breadcrumbs(("Панель администратора", url_for("admin_index")), ("Пользователи", None)))


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html", title="Страница не найдена", breadcrumbs=breadcrumbs(("Ошибка 404", None))), 404


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
else:
    init_db()
