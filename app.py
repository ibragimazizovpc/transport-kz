from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "static/images"
AVATAR_FOLDER = "static/avatars"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["AVATAR_FOLDER"] = AVATAR_FOLDER


def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def is_admin():
    return session.get("username") == "admin"


@app.route("/")
def home():
    search = request.args.get("search", "").strip()
    city = request.args.get("city", "").strip()
    price_min = request.args.get("price_min", "").strip()
    price_max = request.args.get("price_max", "").strip()
    year_min = request.args.get("year_min", "").strip()
    year_max = request.args.get("year_max", "").strip()

    conn = get_db()

    query = """
        SELECT ads.*, users.username, users.avatar,
        (SELECT filename FROM ad_images WHERE ad_images.ad_id = ads.id LIMIT 1) AS first_image
        FROM ads
        LEFT JOIN users ON ads.user_id = users.id
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND ads.title LIKE ?"
        params.append(f"%{search}%")

    if city:
        query += " AND ads.city LIKE ?"
        params.append(f"%{city}%")

    if price_min:
        query += " AND CAST(ads.price AS INTEGER) >= ?"
        params.append(int(price_min))

    if price_max:
        query += " AND CAST(ads.price AS INTEGER) <= ?"
        params.append(int(price_max))

    if year_min:
        query += " AND CAST(ads.year AS INTEGER) >= ?"
        params.append(int(year_min))

    if year_max:
        query += " AND CAST(ads.year AS INTEGER) <= ?"
        params.append(int(year_max))

    query += " ORDER BY ads.id DESC"

    ads = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "index.html",
        ads=ads,
        search=search,
        city=city,
        price_min=price_min,
        price_max=price_max,
        year_min=year_min,
        year_max=year_max,
        username=session.get("username"),
        user_id=session.get("user_id"),
        is_admin=is_admin()
    )


@app.route("/admin")
def admin_panel():
    if not is_admin():
        return "Доступ запрещён"

    conn = get_db()

    users = conn.execute(
        "SELECT * FROM users ORDER BY id DESC"
    ).fetchall()

    ads = conn.execute(
        """
        SELECT ads.*, users.username
        FROM ads
        LEFT JOIN users ON ads.user_id = users.id
        ORDER BY ads.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        users=users,
        ads=ads,
        username=session.get("username")
    )


@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
def admin_delete_user(user_id):
    if not is_admin():
        return "Доступ запрещён"

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if user is None:
        conn.close()
        return redirect("/admin")

    if user["username"] == "admin":
        conn.close()
        return "Нельзя удалить администратора"

    ads = conn.execute(
        "SELECT * FROM ads WHERE user_id = ?",
        (user_id,)
    ).fetchall()

    for ad in ads:
        images = conn.execute(
            "SELECT * FROM ad_images WHERE ad_id = ?",
            (ad["id"],)
        ).fetchall()

        for image in images:
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], image["filename"])
            if os.path.exists(image_path):
                os.remove(image_path)

        conn.execute("DELETE FROM favorites WHERE ad_id = ?", (ad["id"],))
        conn.execute("DELETE FROM messages WHERE ad_id = ?", (ad["id"],))
        conn.execute("DELETE FROM ad_images WHERE ad_id = ?", (ad["id"],))
        conn.execute("DELETE FROM ads WHERE id = ?", (ad["id"],))

    if user["avatar"]:
        avatar_path = os.path.join(app.config["AVATAR_FOLDER"], user["avatar"])
        if os.path.exists(avatar_path):
            os.remove(avatar_path)

    conn.execute("DELETE FROM favorites WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    conn.commit()
    conn.close()

    return redirect("/admin")


@app.route("/admin/delete_ad/<int:ad_id>", methods=["POST"])
def admin_delete_ad(ad_id):
    if not is_admin():
        return "Доступ запрещён"

    conn = get_db()

    ad = conn.execute(
        "SELECT * FROM ads WHERE id = ?",
        (ad_id,)
    ).fetchone()

    if ad is None:
        conn.close()
        return redirect("/admin")

    images = conn.execute(
        "SELECT * FROM ad_images WHERE ad_id = ?",
        (ad_id,)
    ).fetchall()

    for image in images:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], image["filename"])
        if os.path.exists(image_path):
            os.remove(image_path)

    conn.execute("DELETE FROM favorites WHERE ad_id = ?", (ad_id,))
    conn.execute("DELETE FROM messages WHERE ad_id = ?", (ad_id,))
    conn.execute("DELETE FROM ad_images WHERE ad_id = ?", (ad_id,))
    conn.execute("DELETE FROM ads WHERE id = ?", (ad_id,))

    conn.commit()
    conn.close()

    return redirect("/admin")


@app.route("/profile/<int:user_id>")
def profile(user_id):
    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    ads = conn.execute(
        """
        SELECT ads.*,
        (SELECT filename FROM ad_images WHERE ad_images.ad_id = ads.id LIMIT 1) AS first_image
        FROM ads
        WHERE ads.user_id = ?
        ORDER BY ads.id DESC
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    if user is None:
        return "Пользователь не найден"

    return render_template(
        "profile.html",
        user=user,
        ads=ads,
        username=session.get("username"),
        current_user_id=session.get("user_id"),
        is_admin=is_admin()
    )


@app.route("/upload_avatar", methods=["POST"])
def upload_avatar():
    if "user_id" not in session:
        return redirect("/login")

    avatar = request.files["avatar"]

    if avatar and avatar.filename:
        filename = secure_filename(avatar.filename)
        path = os.path.join(app.config["AVATAR_FOLDER"], filename)
        avatar.save(path)

        conn = get_db()
        conn.execute(
            "UPDATE users SET avatar = ? WHERE id = ?",
            (filename, session["user_id"])
        )
        conn.commit()
        conn.close()

    return redirect(f"/profile/{session['user_id']}")


@app.route("/my_ads")
def my_ads():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    ads = conn.execute(
        """
        SELECT ads.*, users.username, users.avatar,
        (SELECT filename FROM ad_images WHERE ad_images.ad_id = ads.id LIMIT 1) AS first_image
        FROM ads
        LEFT JOIN users ON ads.user_id = users.id
        WHERE ads.user_id = ?
        ORDER BY ads.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        ads=ads,
        search="",
        city="",
        price_min="",
        price_max="",
        year_min="",
        year_max="",
        username=session.get("username"),
        user_id=session.get("user_id"),
        is_admin=is_admin()
    )


@app.route("/favorites")
def favorites():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    ads = conn.execute(
        """
        SELECT ads.*, users.username, users.avatar,
        (SELECT filename FROM ad_images WHERE ad_images.ad_id = ads.id LIMIT 1) AS first_image
        FROM favorites
        JOIN ads ON favorites.ad_id = ads.id
        LEFT JOIN users ON ads.user_id = users.id
        WHERE favorites.user_id = ?
        ORDER BY favorites.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        ads=ads,
        search="",
        city="",
        price_min="",
        price_max="",
        year_min="",
        year_max="",
        username=session.get("username"),
        user_id=session.get("user_id"),
        is_admin=is_admin()
    )


@app.route("/messages")
def messages_page():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    chats = conn.execute(
        """
        SELECT
            messages.ad_id,
            ads.title AS ad_title,
            messages.sender_id,
            messages.receiver_id,
            sender.username AS sender_name,
            receiver.username AS receiver_name,
            MAX(messages.id) AS last_message_id
        FROM messages
        JOIN ads ON messages.ad_id = ads.id
        LEFT JOIN users AS sender ON messages.sender_id = sender.id
        LEFT JOIN users AS receiver ON messages.receiver_id = receiver.id
        WHERE messages.sender_id = ? OR messages.receiver_id = ?
        GROUP BY messages.ad_id, messages.sender_id, messages.receiver_id
        ORDER BY last_message_id DESC
        """,
        (session["user_id"], session["user_id"])
    ).fetchall()

    conn.close()

    unique_chats = []
    seen = set()

    for chat in chats:
        other_user_id = chat["receiver_id"] if chat["sender_id"] == session["user_id"] else chat["sender_id"]
        key = (chat["ad_id"], other_user_id)

        if key not in seen:
            seen.add(key)
            unique_chats.append({
                "ad_id": chat["ad_id"],
                "ad_title": chat["ad_title"],
                "other_user_id": other_user_id,
                "other_user_name": chat["receiver_name"] if chat["sender_id"] == session["user_id"] else chat["sender_name"]
            })

    return render_template(
        "messages.html",
        chats=unique_chats,
        username=session.get("username"),
        user_id=session.get("user_id"),
        is_admin=is_admin()
    )


@app.route("/chat/<int:ad_id>/<int:user_id>")
def chat_page(ad_id, user_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    ad = conn.execute(
        """
        SELECT ads.*, users.username
        FROM ads
        LEFT JOIN users ON ads.user_id = users.id
        WHERE ads.id = ?
        """,
        (ad_id,)
    ).fetchone()

    other_user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    messages = conn.execute(
        """
        SELECT messages.*, users.username AS sender_name
        FROM messages
        LEFT JOIN users ON messages.sender_id = users.id
        WHERE messages.ad_id = ?
        AND (
            (messages.sender_id = ? AND messages.receiver_id = ?)
            OR
            (messages.sender_id = ? AND messages.receiver_id = ?)
        )
        ORDER BY messages.id ASC
        """,
        (ad_id, session["user_id"], user_id, user_id, session["user_id"])
    ).fetchall()

    conn.close()

    if ad is None or other_user is None:
        return "Чат не найден"

    return render_template(
        "chat.html",
        ad=ad,
        other_user=other_user,
        messages=messages,
        username=session.get("username"),
        current_user_id=session.get("user_id"),
        is_admin=is_admin()
    )


@app.route("/send_message/<int:ad_id>/<int:user_id>", methods=["POST"])
def send_message(ad_id, user_id):
    if "user_id" not in session:
        return redirect("/login")

    text = request.form["text"].strip()

    if text:
        conn = get_db()
        conn.execute(
            """
            INSERT INTO messages (ad_id, sender_id, receiver_id, text)
            VALUES (?, ?, ?, ?)
            """,
            (ad_id, session["user_id"], user_id, text)
        )
        conn.commit()
        conn.close()

    return redirect(f"/chat/{ad_id}/{user_id}")


@app.route("/favorite/<int:ad_id>")
def add_favorite(ad_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    exists = conn.execute(
        "SELECT * FROM favorites WHERE user_id = ? AND ad_id = ?",
        (session["user_id"], ad_id)
    ).fetchone()

    if not exists:
        conn.execute(
            "INSERT INTO favorites (user_id, ad_id) VALUES (?, ?)",
            (session["user_id"], ad_id)
        )
        conn.commit()

    conn.close()

    return redirect("/")


@app.route("/unfavorite/<int:ad_id>")
def remove_favorite(ad_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    conn.execute(
        "DELETE FROM favorites WHERE user_id = ? AND ad_id = ?",
        (session["user_id"], ad_id)
    )
    conn.commit()
    conn.close()

    return redirect("/favorites")


@app.route("/car/<int:ad_id>")
def car_detail(ad_id):
    conn = get_db()

    ad = conn.execute(
        """
        SELECT ads.*, users.username, users.avatar
        FROM ads
        LEFT JOIN users ON ads.user_id = users.id
        WHERE ads.id = ?
        """,
        (ad_id,)
    ).fetchone()

    if ad is None:
        conn.close()
        return "Объявление не найдено"

    conn.execute(
        "UPDATE ads SET views = views + 1 WHERE id = ?",
        (ad_id,)
    )

    images = conn.execute(
        "SELECT * FROM ad_images WHERE ad_id = ? ORDER BY id ASC",
        (ad_id,)
    ).fetchall()

    conn.commit()

    ad = conn.execute(
        """
        SELECT ads.*, users.username, users.avatar
        FROM ads
        LEFT JOIN users ON ads.user_id = users.id
        WHERE ads.id = ?
        """,
        (ad_id,)
    ).fetchone()

    conn.close()

    is_owner = False
    if "user_id" in session and ad["user_id"] == session["user_id"]:
        is_owner = True

    return render_template(
        "car.html",
        ad=ad,
        images=images,
        username=session.get("username"),
        current_user_id=session.get("user_id"),
        is_owner=is_owner,
        is_admin=is_admin()
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        hashed = generate_password_hash(password)

        conn = get_db()

        existing_user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing_user:
            conn.close()
            return "Такой пользователь уже существует"

        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed)
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):
            session["username"] = user["username"]
            session["user_id"] = user["id"]
            return redirect("/")

        return "Неверный логин"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect("/login")

    title = request.form["title"]
    price = request.form["price"]
    year = request.form["year"]
    city = request.form["city"]
    phone = request.form["phone"]
    description = request.form["description"]

    images = request.files.getlist("images")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO ads (title, price, year, city, description, phone, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (title, price, year, city, description, phone, session["user_id"])
    )

    ad_id = cursor.lastrowid

    for image in images:
        if image and image.filename:
            filename = secure_filename(image.filename)
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(path)

            conn.execute(
                "INSERT INTO ad_images (ad_id, filename) VALUES (?, ?)",
                (ad_id, filename)
            )

    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/delete/<int:ad_id>", methods=["POST"])
def delete(ad_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    ad = conn.execute(
        "SELECT * FROM ads WHERE id = ?",
        (ad_id,)
    ).fetchone()

    if ad is None:
        conn.close()
        return "Объявление не найдено"

    if ad["user_id"] != session["user_id"] and not is_admin():
        conn.close()
        return "Это не ваше объявление"

    images = conn.execute(
        "SELECT * FROM ad_images WHERE ad_id = ?",
        (ad_id,)
    ).fetchall()

    for image in images:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], image["filename"])
        if os.path.exists(image_path):
            os.remove(image_path)

    conn.execute("DELETE FROM favorites WHERE ad_id = ?", (ad_id,))
    conn.execute("DELETE FROM messages WHERE ad_id = ?", (ad_id,))
    conn.execute("DELETE FROM ad_images WHERE ad_id = ?", (ad_id,))
    conn.execute("DELETE FROM ads WHERE id = ?", (ad_id,))

    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/edit/<int:ad_id>")
def edit_page(ad_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    ad = conn.execute(
        "SELECT * FROM ads WHERE id = ?",
        (ad_id,)
    ).fetchone()

    conn.close()

    if ad is None:
        return "Объявление не найдено"

    if ad["user_id"] != session["user_id"] and not is_admin():
        return "Это не ваше объявление"

    return render_template("edit.html", ad=ad)


@app.route("/update/<int:ad_id>", methods=["POST"])
def update(ad_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    ad = conn.execute(
        "SELECT * FROM ads WHERE id = ?",
        (ad_id,)
    ).fetchone()

    if ad is None:
        conn.close()
        return "Объявление не найдено"

    if ad["user_id"] != session["user_id"] and not is_admin():
        conn.close()
        return "Это не ваше объявление"

    title = request.form["title"]
    price = request.form["price"]
    year = request.form["year"]
    city = request.form["city"]
    phone = request.form["phone"]
    description = request.form["description"]

    conn.execute(
        """
        UPDATE ads
        SET title = ?, price = ?, year = ?, city = ?, phone = ?, description = ?
        WHERE id = ?
        """,
        (title, price, year, city, phone, description, ad_id)
    )

    conn.commit()
    conn.close()

    return redirect(f"/car/{ad_id}")


app.run(debug=True)