# -*- coding: utf-8 -*-
"""
定款作成アプリ Blueprint
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.utils import require_roles, ROLES

bp = Blueprint('teikan', __name__, url_prefix='/apps/teikan')


@bp.route('/')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def index():
    """定款アプリトップページ"""
    return render_template('teikan_index.html')


@bp.route('/create', methods=['GET', 'POST'])
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def create():
    """定款作成ページ"""
    if request.method == 'POST':
        # 定款作成処理（今後実装）
        flash('定款を作成しました', 'success')
        return redirect(url_for('teikan.index'))
    
    return render_template('teikan_create.html')


@bp.route('/list')
@require_roles(ROLES["TENANT_ADMIN"], ROLES["SYSTEM_ADMIN"])
def list():
    """定款一覧ページ"""
    # 定款一覧取得（今後実装）
    teikan_list = []
    return render_template('teikan_list.html', teikan_list=teikan_list)
