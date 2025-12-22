# ログイン機能移植完了レポート

## 実行日時
2025年12月22日

## 移植元
**survey-system-app** のログイン機能

## 移植先
**teikan-sakusei-app** (定款作成アプリ)

---

## 移植した機能

### 1. 認証機能 (app/blueprints/auth.py)
- **初回セットアップ**: 最初のシステム管理者作成
- **ログイン選択画面**: システム管理者 / 管理者の選択
- **システム管理者ログイン**: 全テナント横断の最高権限
- **管理者ログイン**: 定款作成・編集権限
- **ログアウト**: セッションクリア
- **CSRF保護**: トークンベースの保護機能
- **パスワード確認**: 新規作成時の二重入力による確認

### 2. データベースユーティリティ (app/utils/db.py)
- **PostgreSQL/SQLite対応**: 環境に応じた自動切り替え
- **スキーマ自動初期化**: T_テナント、T_管理者テーブルの自動作成
- **マルチテナント対応**: tenant_id カラムによるデータ分離
- **プレースホルダ統一**: PostgreSQL (%s) / SQLite (?) の自動変換

### 3. セキュリティユーティリティ (app/utils/security.py)
- **login_user**: セッションへのユーザー情報保存
- **admin_exists**: 管理者存在確認
- **get_csrf**: CSRFトークン生成・取得
- **is_owner**: オーナー権限確認
- **can_manage_system_admins**: システム管理者管理権限確認

### 4. デコレータ (app/utils/decorators.py)
- **require_roles**: ロールベースアクセス制御
- **current_tenant_filter_sql**: テナントフィルタリング
- **ROLES定数**: system_admin, admin の定義

### 5. テンプレート (app/templates/)
- **base.html**: 共通ベーステンプレート
- **login_choice.html**: ログイン選択画面
- **first_setup.html**: 初回セットアップ画面
- **sysadmin_login.html**: システム管理者ログイン画面
- **admin_login.html**: 管理者ログイン画面

---

## データベース設計

### T_テナント (テナントマスタ)
| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INTEGER | 主キー |
| 名称 | TEXT | テナント名 |
| slug | TEXT | URL用スラッグ (UNIQUE) |
| 有効 | INTEGER | 有効フラグ (1=有効) |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

### T_管理者 (管理者マスタ)
| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INTEGER | 主キー |
| login_id | TEXT | ログインID (UNIQUE) |
| name | TEXT | 氏名 |
| password_hash | TEXT | パスワードハッシュ |
| role | TEXT | ロール (system_admin / admin) |
| tenant_id | INTEGER | 所属テナントID (NULL可) |
| active | INTEGER | 有効フラグ (1=有効) |
| is_owner | INTEGER | オーナーフラグ (1=オーナー) |
| can_manage_admins | INTEGER | 管理者管理権限 (1=権限あり) |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

---

## ロール定義

### system_admin (システム管理者)
- **権限**: 全テナント横断の最高権限
- **tenant_id**: NULL (全テナントにアクセス可能)
- **用途**: システム全体の管理、テナント管理

### admin (管理者)
- **権限**: 定款作成・編集
- **tenant_id**: 必須 (所属テナントのみアクセス可能)
- **用途**: 定款の作成・編集・管理

---

## マルチテナント対応

### 設計方針
1. **テナントIDによるデータ分離**: すべての主要テーブルに tenant_id カラムを持たせる
2. **システム管理者の特権**: tenant_id が NULL の場合、全テナントにアクセス可能
3. **テナントフィルタリング**: current_tenant_filter_sql 関数による自動フィルタリング
4. **将来の拡張性**: テナント管理機能、テナント管理者ロールの追加が容易

### 実装済み機能
- ✅ T_テナント テーブル
- ✅ T_管理者.tenant_id カラム
- ✅ テナントフィルタリング関数
- ✅ ロールベースアクセス制御

### 今後の拡張予定
- ⏳ テナント管理画面 (CRUD)
- ⏳ テナント管理者ロール (tenant_admin)
- ⏳ テナント選択機能
- ⏳ テナント間データ分離の強化

---

## セキュリティ機能

### 実装済み
- ✅ **パスワードハッシュ化**: werkzeug.security による安全なハッシュ化
- ✅ **CSRF保護**: トークンベースの保護機能
- ✅ **セッション管理**: Flask session による状態管理
- ✅ **SECRET_KEY**: セッション暗号化用の秘密鍵
- ✅ **パスワード確認**: 新規作成時の二重入力による確認
- ✅ **パスワード最小長**: 8文字以上の強制
- ✅ **ログインID検証**: 英数字と一部記号のみ許可

---

## 動作確認結果

### テスト項目
| 項目 | 結果 | 備考 |
|-----|------|------|
| 初回セットアップページ表示 | ✅ 成功 | first_setup.html 正常表示 |
| システム管理者作成 | ✅ 成功 | データベースに正常保存 |
| ログイン選択画面表示 | ✅ 成功 | login_choice.html 正常表示 |
| システム管理者ログインページ表示 | ✅ 成功 | sysadmin_login.html 正常表示 |
| 管理者ログインページ表示 | ✅ 成功 | admin_login.html 正常表示 |
| データベーステーブル作成 | ✅ 成功 | T_テナント、T_管理者 正常作成 |
| CSRF保護 | ✅ 成功 | トークン生成・検証正常 |

### 作成されたテストデータ
```
ID: 1
ログインID: admin
氏名: テスト管理者
ロール: system_admin
パスワード: admin12345
```

---

## ファイル構成

```
teikan-sakusei-app/
├── app/
│   ├── __init__.py              (修正: auth blueprint登録、get_csrf登録)
│   ├── config.py                (修正: SECRET_KEY追加)
│   ├── blueprints/
│   │   ├── __init__.py
│   │   ├── auth.py              (新規: 認証ルート)
│   │   └── health.py
│   ├── templates/
│   │   ├── base.html            (新規: ベーステンプレート)
│   │   ├── login_choice.html    (新規: ログイン選択)
│   │   ├── first_setup.html     (新規: 初回セットアップ)
│   │   ├── sysadmin_login.html  (新規: システム管理者ログイン)
│   │   └── admin_login.html     (新規: 管理者ログイン)
│   └── utils/
│       ├── __init__.py          (新規: ユーティリティモジュール)
│       ├── db.py                (新規: データベースユーティリティ)
│       ├── security.py          (新規: セキュリティユーティリティ)
│       └── decorators.py        (新規: デコレータ)
├── .env                         (修正: SECRET_KEY追加)
├── .gitignore                   (修正: database/ 追加)
└── database/                    (自動生成: SQLiteデータベース)
    └── teikan_sakusei.db
```

---

## GitHubコミット情報

**コミットハッシュ**: d101b66  
**コミットメッセージ**:
```
feat: Add login functionality from survey-system-app

- Add authentication blueprint with system_admin and admin login
- Add database utilities with PostgreSQL/SQLite support
- Add security utilities (login_user, CSRF protection)
- Add decorators for role-based access control
- Add login templates (login_choice, first_setup, sysadmin_login, admin_login)
- Add multi-tenant support with T_テナント and T_管理者 tables
- Configure SECRET_KEY for session management
```

**変更ファイル数**: 14ファイル  
**追加行数**: 844行  
**削除行数**: 2行

---

## 今後の開発タスク

### 優先度: 高
1. **ダッシュボード実装**: システム管理者・管理者用のダッシュボード画面
2. **管理者管理機能**: 管理者の追加・編集・削除機能
3. **テナント管理機能**: テナントのCRUD機能

### 優先度: 中
4. **パスワード変更機能**: ログイン後のパスワード変更
5. **プロフィール編集**: ユーザー情報の編集機能
6. **アクセス権限管理**: より細かい権限設定

### 優先度: 低
7. **パスワードリセット**: メール経由のパスワードリセット
8. **ログイン履歴**: ログイン履歴の記録・表示
9. **二段階認証**: セキュリティ強化のための二段階認証

---

## 備考

- **マルチテナント対応**: 初期段階から完全対応済み
- **PostgreSQL対応**: Herokuデプロイ時に自動的にPostgreSQLを使用
- **SQLiteフォールバック**: ローカル開発時はSQLiteを自動使用
- **セキュリティ**: パスワード確認、CSRF保護、ハッシュ化など標準的なセキュリティ機能を実装
- **拡張性**: 将来的なテナント管理者ロール、店舗管理などの追加が容易な設計
