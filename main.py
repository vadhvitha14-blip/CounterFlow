"""CounterFlow API (FastAPI + SQLite)."""
import json
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import ai
import db
from services import NAME_KEYS, SERVICES, clean_fields, missing, public

ROLES = ("user", "staff")


@asynccontextmanager
async def lifespan(_):
    db.init()
    yield


app = FastAPI(title="CounterFlow", lifespan=lifespan)


class NewRequest(BaseModel):
    service: str

class AnalyzeIn(BaseModel):
    service: str
    text: str = Field(max_length=1000)
    fields: dict = {}

class VersionIn(BaseModel):
    fields: dict
    author: str
    base_version: Optional[int] = None
    note: str = Field("", max_length=300)

class MessageIn(BaseModel):
    sender: str
    text: str = Field(min_length=1, max_length=500)
    sign: str = ""

class ConfirmIn(BaseModel):
    role: str
    version_no: int


def role_ok(role):
    if role not in ROLES:
        raise HTTPException(422, "role must be 'user' or 'staff'")


def diff(old, new):
    keys = list(dict.fromkeys([*old, *new]))
    return [{"key": k, "old": old.get(k, ""), "new": new.get(k, "")} for k in keys if old.get(k, "") != new.get(k, "")]


def full(rid):
    with db.session() as c:
        r = c.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
        if not r:
            raise HTTPException(404, "Request not found")
        vs = [dict(v) for v in c.execute("SELECT * FROM versions WHERE request_id=? ORDER BY version_no", (rid,))]
        ms = [dict(m) for m in c.execute("SELECT * FROM messages WHERE request_id=? ORDER BY id", (rid,))]
        cs = [dict(x) for x in c.execute("SELECT * FROM confirmations WHERE request_id=? ORDER BY created", (rid,))]
    prev = {}
    for v in vs:
        v["fields"] = json.loads(v["fields"])
        v["changes"] = diff(prev, v["fields"])
        prev = v["fields"]
    cur = vs[-1] if vs else None
    miss = missing(r["service"], cur["fields"] if cur else {})
    done = {x["role"] for x in cs if cur and x["version_no"] == cur["version_no"]}
    if r["cancelled"]:
        status = "cancelled"
    elif not cur or miss:
        status = "needs_info"
    elif done == set(ROLES):
        status = "completed"
    elif done:
        status = "awaiting_" + ("staff" if "user" in done else "user")
    else:
        status = "ready_for_review"
    return {"id": r["id"], "service": r["service"], "service_name": SERVICES[r["service"]]["name"],
            "status": status, "created": r["created"], "updated": r["updated"], "current": cur,
            "original": vs[0] if vs else None, "versions": vs, "messages": ms, "confirmations": cs,
            "confirmed_current": sorted(done), "missing": miss}


def touch(c, rid):
    c.execute("UPDATE requests SET updated=? WHERE id=?", (time.time(), rid))


@app.get("/api/services")
def services():
    return [public(k) for k in SERVICES]


@app.post("/api/analyze")
def analyze(body: AnalyzeIn):
    if body.service not in SERVICES:
        raise HTTPException(404, "Unknown service")
    return ai.analyze(body.service, body.text, body.fields)


@app.post("/api/requests")
def create(body: NewRequest):
    if body.service not in SERVICES:
        raise HTTPException(404, "Unknown service")
    now = time.time()
    with db.session() as c:
        cur = c.execute("INSERT INTO requests(service, created, updated) VALUES(?,?,?)", (body.service, now, now))
        rid = cur.lastrowid
    return full(rid)


@app.get("/api/requests")
def queue(service: Optional[str] = None):
    with db.session() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM requests ORDER BY updated DESC LIMIT 100")]
    out = []
    for rid in ids:
        f = full(rid)
        if service and f["service"] != service:
            continue
        fields = f["current"]["fields"] if f["current"] else {}
        out.append({"id": rid, "service_name": f["service_name"], "status": f["status"], "updated": f["updated"],
                    "version": f["current"]["version_no"] if f["current"] else 0,
                    "who": next((fields[k] for k in NAME_KEYS if fields.get(k)), ""),
                    "purpose": fields.get("purpose", "")})
    return out


@app.get("/api/requests/{rid}")
def get_request(rid: int):
    return full(rid)


@app.post("/api/requests/{rid}/versions")
def add_version(rid: int, body: VersionIn):
    role_ok(body.author)
    state = full(rid)
    if state["status"] in ("completed", "cancelled"):
        raise HTTPException(409, f"This request is {state['status']} and can no longer be changed.")
    cur = state["current"]
    if body.base_version is not None and body.base_version != (cur["version_no"] if cur else 0):
        raise HTTPException(409, "The request was changed by someone else. Please review the latest version first.")
    try:
        fields = clean_fields(state["service"], body.fields)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if cur and fields == cur["fields"]:
        raise HTTPException(422, "Nothing has changed.")
    if not fields:
        raise HTTPException(422, "Please fill in at least one detail.")
    no = (cur["version_no"] if cur else 0) + 1
    try:
        with db.session() as c:
            c.execute("INSERT INTO versions(request_id, version_no, fields, author, note, created) VALUES(?,?,?,?,?,?)",
                      (rid, no, json.dumps(fields), body.author, body.note.strip(), time.time()))
            touch(c, rid)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "The request was changed by someone else. Please review the latest version first.")
    return full(rid)


@app.post("/api/requests/{rid}/messages")
def add_message(rid: int, body: MessageIn):
    role_ok(body.sender)
    state = full(rid)
    with db.session() as c:
        c.execute("INSERT INTO messages(request_id, sender, text, sign, version_no, created) VALUES(?,?,?,?,?,?)",
                  (rid, body.sender, body.text.strip(), body.sign[:30],
                   state["current"]["version_no"] if state["current"] else 0, time.time()))
        touch(c, rid)
    return full(rid)


@app.post("/api/requests/{rid}/confirm")
def confirm(rid: int, body: ConfirmIn):
    role_ok(body.role)
    state = full(rid)
    cur = state["current"]
    if state["status"] == "cancelled":
        raise HTTPException(409, "This request was cancelled.")
    if not cur:
        raise HTTPException(422, "There are no request details to confirm yet.")
    if body.version_no != cur["version_no"]:
        raise HTTPException(409, f"Version {body.version_no} is out of date. The current version is {cur['version_no']}.")
    if state["missing"]:
        raise HTTPException(422, "Some required information is still missing: " + ", ".join(m["label"] for m in state["missing"]))
    with db.session() as c:
        c.execute("INSERT OR IGNORE INTO confirmations(request_id, version_no, role, created) VALUES(?,?,?,?)",
                  (rid, body.version_no, body.role, time.time()))
        touch(c, rid)
    return full(rid)


@app.post("/api/requests/{rid}/cancel")
def cancel(rid: int):
    if full(rid)["status"] == "completed":
        raise HTTPException(409, "A completed request cannot be cancelled.")
    with db.session() as c:
        c.execute("UPDATE requests SET cancelled=1 WHERE id=?", (rid,))
        touch(c, rid)
    return full(rid)


STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
