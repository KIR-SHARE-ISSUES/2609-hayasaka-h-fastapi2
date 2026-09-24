# task_app のフォルダー構成とコードの流れ

## フォルダー構成

フォルダーは「担当する仕事」で分け、ファイル名は「扱うデータ」で分けています。
`tasks.py` はタスク、`names.py` はカテゴリ・担当者（名前だけを持つデータ）を扱います。

```
task_app/
├── main.py              ① 起動：部品を組み立ててアプリを作る
├── config.py               設定：.env・環境変数から接続先を読む
├── errors.py               失敗の種類（NotFoundError など）。全フォルダーから使う
│
├── Views/               ② 画面：ボタン操作 → API へ送信 → 一覧を再描画
│   └── js/app.js, js/api.js
│
├── Controller/          ③ 受付：URL ごとの処理の順番を決める
│   ├── tasks.py            /tasks
│   ├── names.py            /categories, /assignees
│   └── error_handlers.py   例外 → 404 / 409 / 500 の応答に変換
│
├── Schema/              ④ 入口と出口の形：受け取る JSON の検証と、返す JSON の形（Pydantic）
│   ├── base.py
│   ├── tasks.py            TaskCreate / TaskUpdate / TaskResponse
│   └── names.py            CategoryCreate / CategoryResponse など
│
├── DataAccessLayer/     ⑤ DB 操作：SQL の実行と Session（commit / rollback）の管理
│   ├── database.py         Database, execute_database_operation
│   ├── tasks.py            TaskRepository
│   └── names.py            CategoryRepository / AssigneeRepository
│
└── Model/               ⑥ テーブル定義：DB の表・列・関連（SQLAlchemy）
    ├── base.py
    ├── tasks.py            Task
    └── names.py            Category / Assignee
```

**Schema と Model の違い**：Schema は「API でやり取りする JSON の形」、
Model は「DB に保存する表の形」です。同じタスクでも、この 2 つは別々に定義します。

## 依存の向き

矢印の左側のフォルダーが、右側のフォルダーを import します。逆向きの import はありません。

```
main.py → Controller → DataAccessLayer → Model
             ↓
           Schema
（errors.py と config.py は、どこからでも使える共通部品）
```

## 例：タスク新規作成（POST /tasks）を読む順番

| 順 | ファイル | 見る場所 | 何をしているか |
|---|---|---|---|
| 1 | `Views/js/app.js` | `handleCreateTask` | 入力を集めてタイトル必須を確認し、API を呼ぶ |
| 2 | `Views/js/api.js` | `createTask` → `request` | `POST /tasks` に JSON を送る |
| 3 | `main.py` | `TaskApplication.__init__` | `/tasks` が TaskController に登録されている |
| 4 | `Schema/tasks.py` | `TaskCreate` | FastAPI が JSON を検証する（失敗すると 422） |
| 5 | `Controller/tasks.py` | `create` | 関連の確認 → 作成 → 応答作成の順番を決める |
| 6 | `DataAccessLayer/database.py` | `execute_database_operation` | Session を開く → 処理を実行 → commit |
| 7 | `DataAccessLayer/tasks.py` | `create` → `refresh` | INSERT し、ID・日時・関連を読み直す |
| 8 | `Model/tasks.py` | `Task` | どの表・列に保存されるか |
| 9 | `Schema/tasks.py` | `TaskResponse` | 返す JSON の形（201 で返す） |
| 10 | `Controller/error_handlers.py` | `application_error` | 失敗した場合の 404 / 500 への変換 |
| 11 | `Views/js/app.js` | `loadTasks` | 一覧を取得し直して再描画する |

カテゴリ・担当者も同じ順番で、`tasks.py` の代わりに `names.py` を読めば追えます。
