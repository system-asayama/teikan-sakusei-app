# -*- coding: utf-8 -*-
"""
デコレータ
"""

from functools import wraps
from flask import session, redirect, url_for, flash


# ===========================
# 役割定義
# ===========================
ROLES = {
    "SYSTEM_ADMIN": "system_admin",     # 全テナント横断の最高権限
    "ADMIN":        "admin",            # 一般管理者
}


def require_roles(*allowed_roles):
    """指定されたロールのみアクセス可能にするデコレータ"""
    def _decorator(view):
        @wraps(view)
        def _wrapped(*args, **kwargs):
            role = session.get("role")
            if not role or role not in allowed_roles:
                flash("権限がありません。", "warning")
                return redirect(url_for("auth.select_login"))
            return view(*args, **kwargs)
        return _wrapped
    return _decorator


def current_tenant_filter_sql(col_expr: str):
    """
    system_admin 以外は tenant_id で絞る WHERE句 と パラメタを返す。
    col_expr 例: '"T_定款"."tenant_id"'
    戻り値: (where_sql, params_tuple)
    """
    role = session.get("role")
    tenant_id = session.get("tenant_id")
    if role == ROLES["SYSTEM_ADMIN"]:
        return "1=1", ()
    return f"{col_expr} = %s", (tenant_id,)
