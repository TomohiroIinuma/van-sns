import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import re
import os
from streamlit_autorefresh import st_autorefresh

# ------------------------
# 自動更新
# ------------------------
st_autorefresh(interval=3000, limit=None, key="refresh")

# ------------------------
# DB初期化
# ------------------------
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT, content TEXT, user TEXT, category TEXT DEFAULT '未分類',
    image_path TEXT, created_at TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER, parent_id INTEGER DEFAULT 0,
    user TEXT, content TEXT, image_path TEXT, created_at TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS reactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT, target_id INTEGER,
    reaction TEXT, user TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    display_name TEXT,
    icon_path TEXT,
    last_active TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_user TEXT,
    comment_id INTEGER,
    is_read INTEGER DEFAULT 0
)''')
conn.commit()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ------------------------
# 関数
# ------------------------
def set_user(username, display_name, icon_file):
    icon_path = None
    if icon_file:
        icon_path = os.path.join(UPLOAD_DIR, f"{username}_icon.png")
        with open(icon_path, "wb") as f:
            f.write(icon_file.getbuffer())
    last_active = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?)", (username, display_name, icon_path, last_active))
    conn.commit()

def update_user_activity(username):
    last_active = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE users SET last_active=? WHERE username=?", (last_active, username))
    conn.commit()

def add_post(title, content, user, category="未分類", file=None):
    image_path = None
    if file:
        image_path = os.path.join(UPLOAD_DIR, f"{user}_post_{datetime.now().timestamp()}.png")
        with open(image_path, "wb") as f:
            f.write(file.getbuffer())
    c.execute("INSERT INTO posts (title, content, user, category, image_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (title, content, user, category, image_path, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()

def add_comment(post_id, user, content, parent_id=0, file=None):
    image_path = None
    if file:
        image_path = os.path.join(UPLOAD_DIR, f"{user}_comment_{datetime.now().timestamp()}.png")
        with open(image_path, "wb") as f:
            f.write(file.getbuffer())
    c.execute("INSERT INTO comments (post_id, parent_id, user, content, image_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (post_id, parent_id, user, content, image_path, datetime.now().strftime("%Y-%m-%d %H:%M")))
    comment_id = c.lastrowid
    conn.commit()

    # 通知作成（返信・@メンション）
    targets = set()
    if parent_id != 0:
        c.execute("SELECT user FROM comments WHERE id=?", (parent_id,))
        parent_user = c.fetchone()[0]
        if parent_user != user:
            targets.add(parent_user)
    mentioned = re.findall(r"@([A-Za-z0-9_]+)", content)
    for m in mentioned:
        if m != user:
            targets.add(m)
    for t in targets:
        c.execute("INSERT INTO notifications (target_user, comment_id) VALUES (?, ?)", (t, comment_id))
    conn.commit()

def get_posts(search="", category_filter=None):
    query = "SELECT * FROM posts"
    params = []
    conds = []
    if search:
        conds.append("(title LIKE ? OR content LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if category_filter:
        conds.append("category=?")
        params.append(category_filter)
    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY id DESC"
    c.execute(query, params)
    return c.fetchall()

def get_comments(post_id, parent_id=0):
    c.execute("SELECT * FROM comments WHERE post_id=? AND parent_id=? ORDER BY id ASC", (post_id, parent_id))
    return c.fetchall()

# ------------------------
# UI設定
# ------------------------
st.set_page_config(page_title="社内Discord風SNS", layout="wide")
st.markdown("""
<style>
body {background-color: #F0F2F5; color: #333;}
.post-card {background-color: #FFFFFF; border-radius:12px; padding:12px; margin-bottom:15px;}
.comment-card {background-color: #E4E6EB; border-radius:8px; padding:8px; margin-top:5px;}
.comment-unread {background-color: #FFFACD; border-radius:8px; padding:8px; margin-top:5px;}
.mention {color:#1877F2; font-weight:bold;}
.user-info {text-align:center; font-weight:bold; color:#1877F2;}
.online-dot {height:10px;width:10px;background-color:#4CAF50;border-radius:50%;display:inline-block;margin-right:5px;}
</style>
""", unsafe_allow_html=True)

# ------------------------
# マイページ
# ------------------------
st.sidebar.header("👤 マイページ")
username = st.sidebar.text_input("ユーザーID（半角英数字）")
display_name = st.sidebar.text_input("表示名")
icon_file = st.sidebar.file_uploader("アイコン画像", type=["png","jpg"])
if st.sidebar.button("保存"):
    if username and display_name:
        set_user(username, display_name, icon_file)
        st.sidebar.success("保存しました！")

if username:
    update_user_activity(username)

# ------------------------
# 投稿フォーム
# ------------------------
st.subheader("📝 新規投稿")
post_title = st.text_input("タイトル")
post_content = st.text_area("本文")
post_category = st.text_input("カテゴリ", value="未分類")
post_file = st.file_uploader("添付ファイル（任意）", type=["png","jpg","pdf"])
if st.button("投稿する"):
    if username and post_title and post_content:
        add_post(post_title, post_content, username, post_category, post_file)
        st.experimental_rerun()
    else:
        st.warning("ユーザーID、タイトル、本文を入力してください。")

st.markdown("---")

# ------------------------
# 投稿レンダリング
# ------------------------
def render_comments(post_id, parent_id=0, level=0):
    comments = get_comments(post_id, parent_id)
    for c in comments:
        c_id, _, _, c_user, c_content, c_image, c_time = c
        indent = 20 * level
        display_content = re.sub(rf"@{username}", f"<span class='mention'>@{username}</span>", c_content)
        card_class = "comment-card"
        st.markdown(f"<div id='comment_{c_id}' class='{card_class}' style='margin-left:{indent}px'>{c_user} | {c_time}<br>{display_content}</div>", unsafe_allow_html=True)
        if c_image:
            if c_image.endswith(".pdf"):
                st.markdown(f"[PDF]({c_image})")
            else:
                st.image(c_image, width=150)
        # コメント削除ボタン
        if c_user == username or username == "admin":
            if st.button("削除", key=f"del_comment_{c_id}"):
                c.execute("DELETE FROM comments WHERE id=? OR parent_id=?", (c_id, c_id))
                c.execute("DELETE FROM notifications WHERE comment_id=?", (c_id,))
                conn.commit()
                st.experimental_rerun()
        render_comments(post_id, parent_id=c_id, level=level+1)

def render_posts():
    posts = get_posts()
    for post_id, title, content, user, category, image_path, created_at in posts:
        cols = st.columns([1,4])
        with cols[0]:
            st.markdown(f"<div class='user-info'>{user}</div>", unsafe_allow_html=True)
            if image_path and not image_path.endswith(".pdf"):
                st.image(image_path, width=50)
        with cols[1]:
            st.markdown(f"<div class='post-card'>")
            st.markdown(f"**{title}**  _({created_at})_ | カテゴリ: {category}")
            st.markdown(content)
            if image_path:
                if image_path.endswith(".pdf"):
                    st.markdown(f"[PDF]({image_path})")
                else:
                    st.image(image_path, width=200)
            # 投稿削除ボタン
            if user == username or username == "admin":
                if st.button("削除", key=f"del_post_{post_id}"):
                    c.execute("DELETE FROM posts WHERE id=?", (post_id,))
                    c.execute("DELETE FROM comments WHERE post_id=?", (post_id,))
                    c.execute("DELETE FROM notifications WHERE comment_id IN (SELECT id FROM comments WHERE post_id=?)", (post_id,))
                    conn.commit()
                    st.experimental_rerun()
            render_comments(post_id)
            st.markdown("</div>", unsafe_allow_html=True)

render_posts()

# ------------------------
# チームメンバー表示（オンライン優先＋未読バッジ＋スクロール）
# ------------------------
st.sidebar.header("👥 チームメンバー")
c.execute("SELECT display_name, icon_path, last_active, username FROM users")
all_users = c.fetchall()
st.sidebar.markdown(f"**チームメンバー: {len(all_users)}人**")
online_users = []
offline_users = []
for display_name, icon_path, last_active, uname in all_users:
    last_active_time = datetime.strptime(last_active, "%Y-%m-%d %H:%M:%S")
    online = (datetime.now() - last_active_time) < timedelta(seconds=10)
    c.execute("SELECT COUNT(*) FROM notifications WHERE target_user=? AND is_read=0", (uname,))
    unread_count = c.fetchone()[0]
    info = (display_name, icon_path, online, unread_count)
    if online:
        online_users.append(info)
    else:
        offline_users.append(info)
st.sidebar.markdown("<div style='max-height:300px; overflow-y:auto; border:1px solid #DDD; border-radius:8px; padding:5px;'>", unsafe_allow_html=True)
def render_user(display_name, icon_path, online=True, unread=0):
    dot_color = "#4CAF50" if online else "#A0A0A0"
    badge_html = f"<span style='background-color:red;color:white;border-radius:50%;padding:2px 6px;margin-left:5px;font-size:10px;'>{unread}</span>" if unread > 0 else ""
    cols = st.sidebar.columns([1,5])
    with cols[0]:
        if icon_path:
            st.image(icon_path, width=25)
        else:
            st.markdown(f"<span style='height:10px;width:10px;background-color:{dot_color};border-radius:50%;display:inline-block;'></span>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"{display_name} {badge_html}", unsafe_allow_html=True)
for display_name, icon_path, online, unread in online_users:
    render_user(display_name, icon_path, online=True, unread=unread)
for display_name, icon_path, online, unread in offline_users:
    render_user(display_name, icon_path, online=False, unread=unread)
st.sidebar.markdown("</div>", unsafe_allow_html=True)

# ------------------------
# 未読通知リスト
# ------------------------
st.sidebar.header("🔔 未読通知")
if username:
    c.execute("""SELECT n.id, p.title, c.id, c.post_id, c.content
                 FROM notifications n 
                 JOIN comments c ON n.comment_id=c.id 
                 JOIN posts p ON c.post_id=p.id 
                 WHERE n.target_user=? AND n.is_read=0""", (username,))
    notifications = c.fetchall()
    if notifications:
        for notif_id, post_title, comment_id, post_id, comment_content in notifications:
            if st.sidebar.button(f"{post_title}: {comment_content[:20]}...", key=f"notif_{notif_id}"):
                c.execute("UPDATE notifications SET is_read=1 WHERE id=?", (notif_id,))
                conn.commit()
                st.session_state['scroll_to_comment'] = comment_id
                st.experimental_rerun()
    else:
        st.sidebar.write("未読はありません。")

# ------------------------
# 未読コメントジャンプ
# ------------------------
if 'scroll_to_comment' in st.session_state:
    comment_id = st.session_state.pop('scroll_to_comment')
    js = f"""
    <script>
        var elem = document.getElementById('comment_{comment_id}');
        if(elem) {{ elem.scrollIntoView(); elem.style.border='2px solid #FF0000'; }}
    </script>
    """
    st.components.v1.html(js)
