from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional
from pathlib import Path
import aiosqlite
import os
from datetime import datetime

DB_PATH = "planner.db"
ADMIN_TOKEN = os.environ.get("PLANNER_ADMIN_TOKEN", "changeme")  # Koyebで環境変数に設定推奨

app = FastAPI(title="Private Planner")

# --- 静的ファイル ---
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Pydantic モデル ---

class Availability(BaseModel):
    date: str   # "2025-11-20"
    start: str  # "18:00"
    end: str    # "21:00"


class PlanIn(BaseModel):
    name: str = Field(..., max_length=100)
    area: str = Field(..., max_length=200, description="行動範囲")
    availabilities: List[Availability]
    food_dislike: Optional[str] = ""
    food_weak: Optional[str] = ""
    food_cant: Optional[str] = ""
    food_want: Optional[str] = ""


# --- DB 初期化 ---

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              area TEXT NOT NULL,
              availabilities_json TEXT NOT NULL,
              food_dislike TEXT,
              food_weak TEXT,
              food_cant TEXT,
              food_want TEXT,
              created_at TEXT NOT NULL
            );
            """
        )
        await db.commit()


@app.on_event("startup")
async def on_startup():
    await init_db()


# --- ルーティング ---

@app.get("/", response_class=HTMLResponse)
async def index():
    """入力フォームページ"""
    html_path = Path("static/index.html")
    return html_path.read_text(encoding="utf-8")


@app.post("/api/submit")
async def submit(plan: PlanIn):
    """フォーム内容を保存"""
    # 簡易バリデーション：空き時間が1つもない場合はエラー
    if not plan.availabilities:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "空いている日・時間を1つ以上入力してください。"},
        )

    avail_json_lines = []
    for a in plan.availabilities:
        # ここでは文字列のまま保存（必要なら ISO 形式に変換も可）
        avail_json_lines.append(
            {
                "date": a.date,
                "start": a.start,
                "end": a.end,
            }
        )

    import json

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO plans
            (name, area, availabilities_json, food_dislike, food_weak, food_cant, food_want, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan.name,
                plan.area,
                json.dumps(avail_json_lines, ensure_ascii=False),
                plan.food_dislike or "",
                plan.food_weak or "",
                plan.food_cant or "",
                plan.food_want or "",
                datetime.utcnow().isoformat(),
            ),
        )
        await db.commit()

    return {"ok": True}


def require_admin(token: str):
    if token != ADMIN_TOKEN:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    return True


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(token: str):
    """
    あなた専用の確認ページ
    /admin?token=XXXX でアクセス
    """
    require_admin(token)
    # シンプルにHTMLをここで生成（雑でもOKなら）
    # 本気でやるなら templates/admin.html を分けてもよい
    html = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>応募一覧</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          body { font-family: system-ui, sans-serif; padding: 16px; }
          h1 { font-size: 1.4rem; margin-bottom: 1rem; }
          .card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 12px;
            background: #fafafa;
          }
          .name { font-weight: bold; font-size: 1.1rem; }
          .small { color: #666; font-size: 0.85rem; }
          ul { margin: 4px 0 8px 1.2rem; padding: 0; }
        </style>
    </head>
    <body>
      <h1>予定フォームの回答一覧</h1>
      <div id="list">読み込み中...</div>
      <script>
      const params = new URLSearchParams(location.search);
      const token = params.get("token");

      async function load() {
        const res = await fetch(`/api/admin/list?token=${encodeURIComponent(token)}`);
        if (!res.ok) {
          document.getElementById("list").textContent = "読み込みエラー";
          return;
        }
        const data = await res.json();
        const container = document.getElementById("list");
        container.innerHTML = "";
        if (!data.items.length) {
          container.textContent = "まだ回答はありません。";
          return;
        }
        for (const item of data.items) {
          const div = document.createElement("div");
          div.className = "card";
          div.innerHTML = `
            <div class="name">${item.name}</div>
            <div class="small">行動範囲: ${item.area}</div>
            <div class="small">送信日時(UTC): ${item.created_at}</div>
            <div><strong>空いている日・時間</strong>
              <ul>
                ${
                  item.availabilities
                    .map(a => `<li>${a.date} ${a.start}〜${a.end}</li>`)
                    .join("")
                }
              </ul>
            </div>
            <div><strong>嫌いな食べ物</strong>: ${item.food_dislike || "-"}</div>
            <div><strong>苦手な食べ物</strong>: ${item.food_weak || "-"}</div>
            <div><strong>食べられないもの</strong>: ${item.food_cant || "-"}</div>
            <div><strong>今一番食べたいもの</strong>: ${item.food_want || "-"}</div>
          `;
          container.appendChild(div);
        }
      }
      load();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/api/admin/list")
async def admin_list(token: str):
    """管理者用：回答一覧JSON"""
    require_admin(token)
    import json

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM plans ORDER BY id DESC"
        )

    items = []
    for r in rows:
        items.append(
            {
                "id": r["id"],
                "name": r["name"],
                "area": r["area"],
                "availabilities": json.loads(r["availabilities_json"]),
                "food_dislike": r["food_dislike"],
                "food_weak": r["food_weak"],
                "food_cant": r["food_cant"],
                "food_want": r["food_want"],
                "created_at": r["created_at"],
            }
        )
    return {"items": items}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
