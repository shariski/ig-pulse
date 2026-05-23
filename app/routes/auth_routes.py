"""Registration, login, logout."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import auth, registry
from app.config import settings
from app.templating import templates

router = APIRouter()


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse(
        request, "register.html", {"needs_code": bool(settings.register_code)}
    )


@router.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm: str = Form(...),
    code: str = Form(""),
):
    ctx = {"needs_code": bool(settings.register_code), "username": username}
    if settings.register_code and code != settings.register_code:
        ctx["error"] = "Kode undangan salah."
    elif password != confirm:
        ctx["error"] = "Kata sandi tidak cocok."
    elif len(password) < 8:
        ctx["error"] = "Kata sandi minimal 8 karakter."
    if "error" in ctx:
        return templates.TemplateResponse(request, "register.html", ctx)

    conn = registry.connect()
    try:
        if registry.get_user_by_name(conn, username):
            ctx["error"] = "Nama pengguna sudah dipakai."
            return templates.TemplateResponse(request, "register.html", ctx)
        uid = registry.create_user(conn, username, auth.hash_password(password))
    finally:
        conn.close()
    request.session["user_id"] = uid
    return RedirectResponse("/accounts", status_code=302)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = registry.connect()
    try:
        user = registry.get_user_by_name(conn, username)
    finally:
        conn.close()
    if user is None or not auth.verify_password(user["password_hash"], password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Nama pengguna atau kata sandi salah.", "username": username},
        )
    request.session["user_id"] = user["id"]
    return RedirectResponse("/accounts", status_code=302)


@router.post("/logout")
@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)
