import os, sqlite3, secrets, hashlib, hmac, time
from contextlib import contextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field

DB_PATH = os.getenv("DB_PATH", "ros_qii.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-this-admin-token")
TICKET_TTL = int(os.getenv("TICKET_TTL_SECONDS", "86400"))
DEFAULT_DIAMONDS = int(os.getenv("DEFAULT_DIAMONDS", "9999999"))
DEFAULT_GOLD = int(os.getenv("DEFAULT_GOLD", "9999999"))

app = FastAPI(title="ROS QII Independent Test API", version="0.5.0")

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS players (
            username TEXT PRIMARY KEY, salt BLOB NOT NULL, password_hash BLOB NOT NULL,
            diamonds INTEGER NOT NULL, gold INTEGER NOT NULL, level INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS tickets (
            token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, expires_at INTEGER NOT NULL)""")
init_db()

class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=6, max_length=128)

class DiamondUpdate(BaseModel):
    diamonds: int = Field(ge=0, le=2_000_000_000)

class TicketRequest(BaseModel):
    ticket: str = Field(min_length=20, max_length=256)

def player_dict(row):
    return {"username": row["username"], "diamonds": row["diamonds"],
            "gold": row["gold"], "level": row["level"]}

def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)

def make_ticket(username: str):
    raw = secrets.token_urlsafe(36)
    expiry = int(time.time()) + TICKET_TTL
    digest = hashlib.sha256(raw.encode()).hexdigest()
    with db() as c:
        c.execute("INSERT INTO tickets(token_hash, username, expires_at) VALUES(?,?,?)",
                  (digest, username, expiry))
    return raw, expiry

def get_ticket_user(ticket: str):
    digest = hashlib.sha256(ticket.encode()).hexdigest()
    with db() as c:
        row = c.execute("""SELECT t.username, t.expires_at, p.*
            FROM tickets t JOIN players p ON p.username=t.username
            WHERE t.token_hash=?""", (digest,)).fetchone()
        if not row or row["expires_at"] < int(time.time()):
            if row:
                c.execute("DELETE FROM tickets WHERE token_hash=?", (digest,))
            raise HTTPException(401, "Invalid or expired ticket")
        return player_dict(row)

def require_admin(x_admin_token: Optional[str] = Header(default=None)):
    if not x_admin_token or not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(403, "Admin access denied")

@app.get("/health")
def health():
    return {"status": "ok", "service": "ROS QII Independent Test API", "version": "0.5.0"}

@app.post("/register")
def register(data: Credentials):
    salt = secrets.token_bytes(16)
    ph = hash_password(data.password, salt)
    try:
        with db() as c:
            c.execute("""INSERT INTO players(username,salt,password_hash,diamonds,gold,created_at)
                VALUES(?,?,?,?,?,?)""",
                (data.username, salt, ph, DEFAULT_DIAMONDS, DEFAULT_GOLD, int(time.time())))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Username already exists")
    return {"ok": True, "player": {"username": data.username,
            "diamonds": DEFAULT_DIAMONDS, "gold": DEFAULT_GOLD, "level": 1}}

@app.post("/v2/ros/login_mobile_ios_v2")
def login(data: Credentials):
    with db() as c:
        row = c.execute("SELECT * FROM players WHERE username=?", (data.username,)).fetchone()
    if not row or not hmac.compare_digest(hash_password(data.password, row["salt"]), row["password_hash"]):
        raise HTTPException(401, "Incorrect username or password")
    ticket, expiry = make_ticket(data.username)
    return {"ok": True, "ticket": ticket, "expires_at": expiry,
            "player": player_dict(row)}

@app.post("/v2/ros/relaunch_mobile_ios_v2")
def relaunch(data: TicketRequest):
    return {"ok": True, "player": get_ticket_user(data.ticket)}

@app.post("/v2/account/rosl/exchangeTicket")
def exchange_ticket(data: TicketRequest):
    return {"ok": True, "player": get_ticket_user(data.ticket)}


@app.get("/me")
def me(x_ticket: Optional[str] = Header(default=None)):
    if not x_ticket:
        raise HTTPException(401, "X-Ticket header required")
    return {"player": get_ticket_user(x_ticket)}

@app.delete("/session")
def logout(x_ticket: Optional[str] = Header(default=None)):
    if not x_ticket:
        raise HTTPException(401, "X-Ticket header required")
    digest = hashlib.sha256(x_ticket.encode()).hexdigest()
    with db() as c:
        cur = c.execute("DELETE FROM tickets WHERE token_hash=?", (digest,))
    if cur.rowcount == 0:
        raise HTTPException(401, "Invalid or expired ticket")
    return {"ok": True}

@app.get("/v2/ros/online-count")
def online_count():
    with db() as c:
        count = c.execute("SELECT COUNT(*) FROM tickets WHERE expires_at>=?", (int(time.time()),)).fetchone()[0]
    return {"online": count}

@app.get("/player/{username}")
def profile(username: str):
    with db() as c:
        row = c.execute("SELECT * FROM players WHERE username=?", (username,)).fetchone()
    if not row:
        raise HTTPException(404, "Player not found")
    return {"player": player_dict(row)}

@app.get("/lobby")
def lobby():
    return {"ok": True, "modes": ["solo", "duo", "squad"], "notice": "Test lobby only; no live battle server."}

@app.post("/queue/{mode}")
def queue(mode: str, x_ticket: Optional[str] = Header(default=None)):
    if mode not in {"solo", "duo", "squad"}:
        raise HTTPException(400, "Unsupported mode")
    if not x_ticket:
        raise HTTPException(401, "X-Ticket header required")
    player = get_ticket_user(x_ticket)
    return {"ok": True, "status": "queued_test_only", "mode": mode, "username": player["username"]}

@app.get("/admin/players", dependencies=[Depends(require_admin)])
def admin_players():
    with db() as c:
        rows = c.execute("SELECT * FROM players ORDER BY username").fetchall()
    return {"players": [player_dict(r) for r in rows]}

@app.post("/admin/players/{username}/diamonds", dependencies=[Depends(require_admin)])
def set_diamonds(username: str, data: DiamondUpdate):
    with db() as c:
        cur = c.execute("UPDATE players SET diamonds=? WHERE username=?", (data.diamonds, username))
        if cur.rowcount == 0:
            raise HTTPException(404, "Player not found")
    return {"ok": True, "username": username, "diamonds": data.diamonds}
