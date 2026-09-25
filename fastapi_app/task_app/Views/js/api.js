/**
 * TaskApiはHTTP通信、ApiErrorは画面に渡す失敗情報を担当する。
 * TaskAppから依頼を受け、ControllerのAPIへJSONを送り、応答や失敗を返す。
 */
export const API_BASE_URL = "http://localhost:8888";

export class ApiError extends Error {
  constructor(message, status, detail = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** 接続先と通信手段を持つAPIクライアント。リトライによる二重登録を避ける。 */
export class TaskApi {
  constructor(baseUrl = API_BASE_URL, fetchImpl = (...args) => fetch(...args)) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetchImpl = fetchImpl;
  }

  /** 422の項目別エラーと、404/409などの文字列エラーを画面表示用に整える。 */
  formatDetail(detail) {
    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          const location = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "入力";
          return `${location || "入力"}: ${item.msg ?? "値を確認してください"}`;
        })
        .join(" / ");
    }

    return "API リクエストに失敗しました。";
  }

  /** JSON通信と失敗分類を集約する。HTTP失敗・通信断・不正な応答はApiErrorで呼び出し元へ返す。
   * DELETE成功の204には本文がないため解析しない。書き込みは自動再試行しない。
   */
  async request(path, options = {}) {
    const headers = {
      Accept: "application/json",
      ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    };
    let response;
    try {
      response = await this.fetchImpl(this.baseUrl + path, { ...options, headers });
    } catch (error) {
      throw new ApiError(
        "API に接続できません。FastAPI が " + this.baseUrl + " で起動しているか確認してください。",
        0,
        error,
      );
    }

    if (!response.ok) {
      let detail;
      try {
        const text = await response.text();
        try {
          const body = JSON.parse(text);
          detail = body.detail ?? body;
        } catch {
          detail = text || null;
        }
      } catch (error) {
        throw new ApiError("API のエラー応答を読み取れませんでした。", response.status, error);
      }
      throw new ApiError(this.formatDetail(detail), response.status, detail);
    }

    if (response.status === 204) {
      return null;
    }
    try {
      return await response.json();
    } catch (error) {
      throw new ApiError(
        "API から正しい JSON 応答を受け取れませんでした。",
        response.status,
        error,
      );
    }
  }

  /** 画面の状態名をAPIの真偽値へ変換して検索する。未指定の条件はURLに含めない。 */
  getTasks({ status = "all", categoryId = null } = {}) {
    const query = new URLSearchParams();

    if (status === "open") {
      query.set("is_done", "false");
    } else if (status === "done") {
      query.set("is_done", "true");
    }
    if (categoryId !== null && categoryId !== "") {
      query.set("category_id", String(categoryId));
    }

    const suffix = query.size > 0 ? `?${query.toString()}` : "";
    return this.request(`/tasks${suffix}`);
  }

  /** 編集前に1件を取得する。未存在の404は共通requestがApiErrorに変換する。 */
  getTask(taskId) {
    return this.request(`/tasks/${taskId}`);
  }

  /** 作成用の4項目を送る。成功したPromiseはサーバーの保存確定後の応答を持つ。 */
  createTask(payload) {
    return this.request("/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  /** 全5項目をPUTする。nullは関連解除を意味し、省略はAPIの422になる。 */
  updateTask(taskId, payload) {
    return this.request(`/tasks/${taskId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  /** DELETEの成功時はnullを返す。削除失敗を成功として扱わない。 */
  deleteTask(taskId) {
    return this.request(`/tasks/${taskId}`, { method: "DELETE" });
  }

  /** カテゴリの選択肢を取得する。画面への反映はTaskAppが担当する。 */
  getCategories() {
    return this.request("/categories");
  }

  /** カテゴリ名を送る。名前重複の409もほかのHTTPエラーと同じ経路で伝える。 */
  createCategory(payload) {
    return this.request("/categories", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  /** 担当者の選択肢を取得する。画面への反映はTaskAppが担当する。 */
  getAssignees() {
    return this.request("/assignees");
  }

  /** 担当者名を送る。名前重複の409もほかのHTTPエラーと同じ経路で伝える。 */
  createAssignee(payload) {
    return this.request("/assignees", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
}
