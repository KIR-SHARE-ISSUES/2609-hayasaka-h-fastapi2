/**
 * TaskAppは画面状態・イベント・DOM更新を担当する。
 * 通信は注入したTaskApiへ委譲し、成功・失敗後に入力や一覧をどう見せるかを決める。
 * 入力 → TaskApiで送信 → 成功時に一覧更新、の順に進め、保存失敗時は入力を残す。
 */
import { TaskApi } from "./api.js";

export class TaskApp {
  constructor(api = new TaskApi(), root = document, view = window) {
    this.api = api;
    this.document = root;
    this.window = view;
    this.initialized = false;
    this.feedbackTimer = null;
    this.latestTaskRequest = 0;
    this.latestEditRequest = 0;
    this.state = {
      tasks: [],
      categories: [],
      assignees: [],
      filters: {
        status: "all",
        categoryId: null,
      },
      editingTaskId: null,
      tasksLoaded: false,
      categoryTargetSelectId: null,
      assigneeTargetSelectId: null,
    };
    this.elements = {
      createForm: this.document.querySelector("#task-create-form"),
      createTitle: this.document.querySelector("#task-title"),
      createDescription: this.document.querySelector("#task-description"),
      createCategory: this.document.querySelector("#task-category"),
      createAssignee: this.document.querySelector("#task-assignee"),
      createTaskButton: this.document.querySelector("#create-task-button"),

      statusTabs: [...this.document.querySelectorAll("[data-status]")],
      filterCategory: this.document.querySelector("#filter-category"),
      refreshTasks: this.document.querySelector("#refresh-tasks"),
      feedback: this.document.querySelector("#feedback"),
      taskCount: this.document.querySelector("#task-count"),
      activeFilterLabel: this.document.querySelector("#active-filter-label"),
      loadingState: this.document.querySelector("#loading-state"),
      taskList: this.document.querySelector("#task-list"),
      emptyState: this.document.querySelector("#empty-state"),

      editDialog: this.document.querySelector("#edit-task-dialog"),
      editForm: this.document.querySelector("#task-edit-form"),
      editTitle: this.document.querySelector("#edit-title"),
      editDescription: this.document.querySelector("#edit-description"),
      editCategory: this.document.querySelector("#edit-category"),
      editAssignee: this.document.querySelector("#edit-assignee"),
      editIsDone: this.document.querySelector("#edit-is-done"),
      saveTaskButton: this.document.querySelector("#save-task-button"),

      categoryDialog: this.document.querySelector("#category-dialog"),
      categoryForm: this.document.querySelector("#category-form"),
      categoryName: this.document.querySelector("#category-name"),
      createCategoryButton: this.document.querySelector("#create-category-button"),

      assigneeDialog: this.document.querySelector("#assignee-dialog"),
      assigneeForm: this.document.querySelector("#assignee-form"),
      assigneeName: this.document.querySelector("#assignee-name"),
      createAssigneeButton: this.document.querySelector("#create-assignee-button"),
    };
  }

  /** イベントは一度だけ登録し、初期データを読み込む。APIの取得失敗は画面に表示する。 */
  async initialize() {
    if (this.initialized) {
      return;
    }
    this.initialized = true;
    this.bindEvents();
    await this.refreshData();
  }

  /** 一覧と選択肢を並行取得する。一部の取得失敗でも成功した選択肢は利用できる。 */
  async refreshData({ announce = false } = {}) {
    const [categories, assignees, tasks] = await Promise.allSettled([
      this.api.getCategories(),
      this.api.getAssignees(),
      this.loadTasks(),
    ]);

    if (categories.status === "fulfilled") {
      this.state.categories = categories.value;
      this.renderCategorySelects();
    }
    if (assignees.status === "fulfilled") {
      this.state.assignees = assignees.value;
      this.renderAssigneeSelects();
    }
    this.elements.activeFilterLabel.textContent = this.buildFilterLabel();

    const failed = [categories, assignees, tasks].find((result) => result.status === "rejected");
    if (failed) {
      this.showFeedback(failed.reason.message, "error");
    } else if (tasks.value) {
      if (announce) {
        this.showFeedback("タスク一覧と選択肢を更新しました。", "success");
      }
    }
  }

  /** 再描画してもイベントが増えないよう、初期化時にだけ登録する。コールバックのthisを固定する。 */
  bindEvents() {
    this.elements.createForm.addEventListener("submit", this.handleCreateTask.bind(this));
    this.elements.editForm.addEventListener("submit", this.handleUpdateTask.bind(this));
    this.elements.categoryForm.addEventListener("submit", this.handleCreateCategory.bind(this));
    this.elements.assigneeForm.addEventListener("submit", this.handleCreateAssignee.bind(this));

    this.elements.statusTabs.forEach((tab) => {
      tab.addEventListener("click", () => this.changeStatusFilter(tab.dataset.status));
    });

    this.elements.filterCategory.addEventListener("change", () => {
      this.state.filters.categoryId = this.toNullableId(this.elements.filterCategory.value);
      this.loadTasks();
    });

    this.elements.refreshTasks.addEventListener("click", () =>
      this.refreshData({ announce: true }),
    );

    this.document.querySelectorAll("input[required]").forEach((input) => {
      input.addEventListener("input", () => input.setCustomValidity(""));
    });
    this.elements.taskList.addEventListener("click", this.handleTaskListClick.bind(this));
    this.elements.taskList.addEventListener("change", this.handleTaskListChange.bind(this));

    this.document.querySelectorAll("[data-open-category-dialog]").forEach((button) => {
      button.addEventListener("click", () => {
        this.state.categoryTargetSelectId = button.dataset.targetSelect;
        this.openDialog(this.elements.categoryDialog, this.elements.categoryName);
      });
    });

    this.document.querySelectorAll("[data-open-assignee-dialog]").forEach((button) => {
      button.addEventListener("click", () => {
        this.state.assigneeTargetSelectId = button.dataset.targetSelect;
        this.openDialog(this.elements.assigneeDialog, this.elements.assigneeName);
      });
    });

    this.document.querySelectorAll("[data-close-dialog]").forEach((button) => {
      button.addEventListener("click", () => {
        const dialog = this.document.querySelector(`#${button.dataset.closeDialog}`);
        this.closeDialog(dialog);
      });
    });
    [this.elements.editDialog, this.elements.categoryDialog, this.elements.assigneeDialog].forEach(
      (dialog) => {
        dialog.addEventListener("click", (event) => {
          if (event.target === dialog) {
            this.closeDialog(dialog);
          }
        });
        dialog.addEventListener("cancel", (event) => {
          if (dialog.querySelector('form[aria-busy="true"]')) {
            event.preventDefault();
          }
        });
      },
    );

    this.elements.editDialog.addEventListener("close", () => {
      this.state.editingTaskId = null;
      this.elements.editForm.reset();
    });

    this.elements.categoryDialog.addEventListener("close", () => {
      this.elements.categoryForm.reset();
      this.state.categoryTargetSelectId = null;
    });

    this.elements.assigneeDialog.addEventListener("close", () => {
      this.elements.assigneeForm.reset();
      this.state.assigneeTargetSelectId = null;
    });
  }

  /** 画面入力をPOSTの契約に合わせる。空欄はnull、選択したIDは数値へ変換する。 */
  buildCreatePayload() {
    return {
      title: this.elements.createTitle.value.trim(),
      description: this.toNullableText(this.elements.createDescription.value),
      category_id: this.toNullableId(this.elements.createCategory.value),
      assignee_id: this.toNullableId(this.elements.createAssignee.value),
    };
  }

  /** 入力確認→POST→一覧再取得の順で進める。POST失敗時は入力を残し、二重送信を抑える。 */
  async handleCreateTask(event) {
    event.preventDefault();
    const payload = this.buildCreatePayload();

    if (
      !this.validateRequiredText(
        payload.title,
        this.elements.createTitle,
        "タイトルを入力してください。",
      )
    ) {
      return;
    }

    this.setFormBusy(this.elements.createForm, true);
    try {
      await this.api.createTask(payload);
      this.elements.createForm.reset();
      await this.loadTasks({ successMessage: "タスクを追加しました。" });
      this.window.requestAnimationFrame(() => this.elements.createTitle.focus());
    } catch (error) {
      this.showFeedback(error.message, "error");
    } finally {
      this.setFormBusy(this.elements.createForm, false);
    }
  }

  /** 現在の条件で一覧を取得する。古い応答を捨て、保存成功後の再取得失敗は区別して表示する。
   */
  async loadTasks({ successMessage = null } = {}) {
    const requestNumber = ++this.latestTaskRequest;
    this.setTaskListLoading(true);

    try {
      const tasks = await this.api.getTasks(this.state.filters);
      if (requestNumber !== this.latestTaskRequest) {
        return false;
      }

      this.state.tasks = tasks;
      this.state.tasksLoaded = true;
      this.renderTasks();

      if (successMessage) {
        this.showFeedback(successMessage, "success");
      }
      return true;
    } catch (error) {
      if (requestNumber === this.latestTaskRequest) {
        this.state.tasks = [];
        this.state.tasksLoaded = false;
        this.renderTasks();
        const prefix = successMessage
          ? "変更は保存されましたが、一覧を再取得できませんでした。"
          : "";
        this.showFeedback(`${prefix}${error.message}`, "error");
      }
      return false;
    } finally {
      if (requestNumber === this.latestTaskRequest) {
        this.setTaskListLoading(false);
      }
    }
  }

  /** 選択状態を更新してAPIで再検索する。Falseと未指定の変換はTaskApiに任せる。 */
  changeStatusFilter(status) {
    this.state.filters.status = status;

    this.elements.statusTabs.forEach((tab) => {
      const selected = tab.dataset.status === status;
      tab.classList.toggle("is-active", selected);
      tab.setAttribute("aria-pressed", String(selected));
    });

    this.loadTasks();
  }

  /** 一覧の取得状態とカードを描画する。ユーザー入力はtextContentで扱い、HTMLとして実行しない。 */
  renderTasks() {
    this.elements.taskList.replaceChildren();
    this.elements.taskCount.textContent = this.state.tasksLoaded
      ? `${this.state.tasks.length} 件を表示`
      : "一覧を取得できませんでした";
    this.elements.activeFilterLabel.textContent = this.buildFilterLabel();

    if (!this.state.tasksLoaded) {
      this.elements.emptyState.hidden = true;
      return;
    }

    this.elements.emptyState.hidden = this.state.tasks.length !== 0;
    this.state.tasks.forEach((task) => this.elements.taskList.append(this.createTaskCard(task)));
  }

  /** 1件の応答からカードを作る。未設定の関連と説明も表示できるようにする。 */
  createTaskCard(task) {
    const item = this.document.createElement("li");
    item.className = "task-card";
    item.dataset.taskId = String(task.id);
    item.classList.toggle("is-done", task.is_done);

    const checkLabel = this.document.createElement("label");
    checkLabel.className = "task-check";

    const checkbox = this.document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = task.is_done;
    checkbox.dataset.action = "toggle";
    checkbox.dataset.taskId = String(task.id);
    checkbox.setAttribute("aria-label", `${task.title}を${task.is_done ? "未完了" : "完了"}にする`);
    checkLabel.append(checkbox);

    const content = this.document.createElement("div");
    content.className = "task-card__content";

    const titleRow = this.document.createElement("div");
    titleRow.className = "task-card__title-row";

    const title = this.document.createElement("h3");
    title.className = "task-card__title";
    title.textContent = task.title;

    const status = this.document.createElement("span");
    status.className = `status-pill ${task.is_done ? "status-pill--done" : "status-pill--open"}`;
    status.textContent = task.is_done ? "完了" : "未完了";
    titleRow.append(title, status);

    const description = this.document.createElement("p");
    description.className = "task-card__description";
    description.textContent = task.description || "説明はありません";
    description.classList.toggle("is-placeholder", !task.description);

    const meta = this.document.createElement("div");
    meta.className = "task-card__meta";
    meta.append(
      this.createTag(task.category?.name ?? "カテゴリ未設定", "category", !task.category),
      this.createTag(task.assignee?.name ?? "担当者未設定", "assignee", !task.assignee),
    );

    if (task.updated_at) {
      const updated = this.document.createElement("time");
      updated.className = "task-card__updated";
      updated.dateTime = task.updated_at;
      updated.textContent = `更新 ${this.formatDateTime(task.updated_at)}`;
      meta.append(updated);
    }

    content.append(titleRow, description, meta);

    const actions = this.document.createElement("div");
    actions.className = "task-card__actions";
    actions.append(
      this.createActionButton("編集", "edit", task, "button--secondary"),
      this.createActionButton("削除", "delete", task, "button--danger"),
    );

    item.append(checkLabel, content, actions);
    return item;
  }

  /** 関連名をテキスト表示する。未設定の見た目はクラス名で区別する。 */
  createTag(label, kind, isEmpty) {
    const tag = this.document.createElement("span");
    tag.className = `tag tag--${kind}`;
    tag.classList.toggle("tag--empty", isEmpty);
    tag.textContent = label;
    return tag;
  }

  /** 一覧の親でイベントを受けるため、操作種別とタスクIDをボタンに設定する。 */
  createActionButton(label, action, task, className) {
    const button = this.document.createElement("button");
    button.type = "button";
    button.className = `button button--small ${className}`;
    button.dataset.action = action;
    button.dataset.taskId = String(task.id);
    button.textContent = label;
    button.setAttribute("aria-label", `${task.title}を${label}`);
    return button;
  }

  /** 動的に作られたカードから操作とIDを取り出し、編集・削除へ渡す。 */
  handleTaskListClick(event) {
    const button = event.target.closest("button[data-action]");
    if (!button) {
      return;
    }

    const taskId = Number(button.dataset.taskId);
    if (button.dataset.action === "edit") {
      this.openEditDialog(taskId);
    } else if (button.dataset.action === "delete") {
      this.handleDeleteTask(taskId);
    }
  }

  /** 完了チェックの変更をAPI更新へ渡す。保存結果の表示はhandleToggleTaskが担当する。 */
  handleTaskListChange(event) {
    const checkbox = event.target.closest('input[data-action="toggle"]');
    if (!checkbox) {
      return;
    }

    this.handleToggleTask(Number(checkbox.dataset.taskId), checkbox.checked);
  }

  /** 一覧のタスクから全項目PUTを送る。失敗時は元の一覧を描画し、エラーを表示する。
   * 別タブとの競合検出は未実装のため、古い一覧からの更新で他の編集を上書きし得る。 */
  async handleToggleTask(taskId, nextDoneValue) {
    const task = this.state.tasks.find((candidate) => candidate.id === taskId);
    if (!task) {
      return;
    }

    this.setTaskCardBusy(taskId, true);
    try {
      await this.api.updateTask(taskId, this.taskToUpdatePayload(task, nextDoneValue));
      await this.loadTasks({
        successMessage: nextDoneValue ? "タスクを完了にしました。" : "タスクを未完了に戻しました。",
      });
    } catch (error) {
      this.renderTasks();
      this.showFeedback(error.message, "error");
    } finally {
      this.setTaskCardBusy(taskId, false);
    }
  }

  /** 関連オブジェクトからIDを取り出し、PUTの全5項目を構成する。 */
  taskToUpdatePayload(task, isDone = task.is_done) {
    return {
      title: task.title,
      description: task.description,
      is_done: isDone,
      category_id: task.category?.id ?? null,
      assignee_id: task.assignee?.id ?? null,
    };
  }

  /** 最新データと選択肢を取得して編集欄へ設定する。後から届いた古い編集要求の応答は捨てる。 */
  async openEditDialog(taskId) {
    const requestNumber = ++this.latestEditRequest;
    this.setTaskCardBusy(taskId, true);
    try {
      const [task, categories, assignees] = await Promise.all([
        this.api.getTask(taskId),
        this.api.getCategories(),
        this.api.getAssignees(),
      ]);
      if (requestNumber !== this.latestEditRequest) {
        return;
      }
      this.state.categories = categories;
      this.state.assignees = assignees;
      this.state.editingTaskId = task.id;
      this.renderCategorySelects();
      this.renderAssigneeSelects();
      this.elements.editTitle.value = task.title;
      this.elements.editDescription.value = task.description ?? "";
      this.elements.editCategory.value = task.category ? String(task.category.id) : "";
      this.elements.editAssignee.value = task.assignee ? String(task.assignee.id) : "";
      this.elements.editIsDone.checked = task.is_done;

      this.openDialog(this.elements.editDialog, this.elements.editTitle);
    } catch (error) {
      if (requestNumber === this.latestEditRequest) {
        this.showFeedback(error.message, "error");
      }
    } finally {
      this.setTaskCardBusy(taskId, false);
    }
  }

  /** 全項目PUTの成功後にダイアログを閉じる。失敗時は入力を保持して再編集できるようにする。 */
  async handleUpdateTask(event) {
    event.preventDefault();
    if (this.state.editingTaskId === null) {
      return;
    }

    const payload = {
      title: this.elements.editTitle.value.trim(),
      description: this.toNullableText(this.elements.editDescription.value),
      is_done: this.elements.editIsDone.checked,
      category_id: this.toNullableId(this.elements.editCategory.value),
      assignee_id: this.toNullableId(this.elements.editAssignee.value),
    };

    if (
      !this.validateRequiredText(
        payload.title,
        this.elements.editTitle,
        "タイトルを入力してください。",
      )
    ) {
      return;
    }

    const taskId = this.state.editingTaskId;
    this.setFormBusy(this.elements.editForm, true);
    try {
      await this.api.updateTask(taskId, payload);
      this.elements.editDialog.close();
      await this.loadTasks({ successMessage: "タスクを更新しました。" });
    } catch (error) {
      this.showFeedback(error.message, "error");
    } finally {
      this.setFormBusy(this.elements.editForm, false);
    }
  }

  /** ユーザーの確認後に削除する。失敗を表示し、キャンセル時にはAPIを呼ばない。 */
  async handleDeleteTask(taskId) {
    const task = this.state.tasks.find((candidate) => candidate.id === taskId);
    if (!task) {
      return;
    }

    if (!this.window.confirm(`「${task.title}」を削除しますか？`)) {
      return;
    }

    this.setTaskCardBusy(taskId, true);
    try {
      await this.api.deleteTask(taskId);
      await this.loadTasks({ successMessage: "タスクを削除しました。" });
    } catch (error) {
      this.showFeedback(error.message, "error");
    } finally {
      this.setTaskCardBusy(taskId, false);
    }
  }

  /** 登録成功後にカテゴリ選択肢を更新する。失敗時はダイアログ内に理由を表示する。 */
  async handleCreateCategory(event) {
    event.preventDefault();
    const name = this.elements.categoryName.value.trim();
    if (
      !this.validateRequiredText(name, this.elements.categoryName, "カテゴリ名を入力してください。")
    ) {
      return;
    }

    const targetSelectId = this.state.categoryTargetSelectId;
    this.setFormBusy(this.elements.categoryForm, true);
    try {
      const created = await this.api.createCategory({ name });
      this.state.categories = this.upsertAndSort(this.state.categories, created);
      this.renderCategorySelects(targetSelectId, created.id);
      this.elements.categoryDialog.close();
      this.showFeedback(`カテゴリ「${created.name}」を追加しました。`, "success");
      this.focusSelectLater(targetSelectId);
    } catch (error) {
      this.showFeedback(error.message, "error");
    } finally {
      this.setFormBusy(this.elements.categoryForm, false);
    }
  }

  /** 登録成功後に担当者選択肢を更新する。失敗時はダイアログ内に理由を表示する。 */
  async handleCreateAssignee(event) {
    event.preventDefault();
    const name = this.elements.assigneeName.value.trim();
    if (
      !this.validateRequiredText(name, this.elements.assigneeName, "担当者名を入力してください。")
    ) {
      return;
    }

    const targetSelectId = this.state.assigneeTargetSelectId;
    this.setFormBusy(this.elements.assigneeForm, true);
    try {
      const created = await this.api.createAssignee({ name });
      this.state.assignees = this.upsertAndSort(this.state.assignees, created);
      this.renderAssigneeSelects(targetSelectId, created.id);
      this.elements.assigneeDialog.close();
      this.showFeedback(`担当者「${created.name}」を追加しました。`, "success");
      this.focusSelectLater(targetSelectId);
    } catch (error) {
      this.showFeedback(error.message, "error");
    } finally {
      this.setFormBusy(this.elements.assigneeForm, false);
    }
  }

  /** 新規・編集・絞り込みの選択肢をそろえ、追加元には作成したカテゴリを選択する。 */
  renderCategorySelects(targetSelectId = null, createdId = null) {
    this.replaceSelectOptions(this.elements.createCategory, this.state.categories, "未設定");
    this.replaceSelectOptions(this.elements.editCategory, this.state.categories, "未設定");
    this.replaceSelectOptions(
      this.elements.filterCategory,
      this.state.categories,
      "すべてのカテゴリ",
      this.state.filters.categoryId,
    );

    this.selectCreatedOption(targetSelectId, createdId);
  }

  /** 新規・編集の選択肢をそろえ、追加元には作成した担当者を選択する。 */
  renderAssigneeSelects(targetSelectId = null, createdId = null) {
    this.replaceSelectOptions(this.elements.createAssignee, this.state.assignees, "未設定");
    this.replaceSelectOptions(this.elements.editAssignee, this.state.assignees, "未設定");
    this.selectCreatedOption(targetSelectId, createdId);
  }

  /** 選択肢を作り直して既存の選択を保つ。選択先が消えていれば未設定へ戻す。 */
  replaceSelectOptions(select, items, placeholder, desiredValue = select.value) {
    const previousValue = desiredValue === null ? "" : String(desiredValue);
    const placeholderOption = new this.window.Option(placeholder, "");
    const options = items.map((item) => new this.window.Option(item.name, String(item.id)));
    select.replaceChildren(placeholderOption, ...options);

    const valueStillExists = [...select.options].some((option) => option.value === previousValue);
    select.value = valueStillExists ? previousValue : "";
  }

  /** 登録を開始した選択欄に新しいIDを設定する。対象がなくなっていれば何もしない。 */
  selectCreatedOption(targetSelectId, createdId) {
    if (!targetSelectId || createdId === null) {
      return;
    }

    const target = this.document.querySelector(`#${targetSelectId}`);
    if (target) {
      target.value = String(createdId);
    }
  }

  /** 重複するIDを置き換えて昇順にする。元の配列を直接変更しない。 */
  upsertAndSort(items, created) {
    return [...items.filter((item) => item.id !== created.id), created].sort((a, b) => a.id - b.id);
  }

  /** 前回の通知を隠し、入力欄へフォーカスを移す。すでに開いている場合も入力先を更新する。 */
  openDialog(dialog, initialFocus) {
    dialog.querySelector("[data-dialog-feedback]").hidden = true;
    if (!dialog.open) {
      dialog.showModal();
    }
    this.window.requestAnimationFrame(() => initialFocus?.focus());
  }

  /** 送信中のダイアログは閉じず、処理結果を確認できるようにする。 */
  closeDialog(dialog) {
    if (dialog && !dialog.querySelector('form[aria-busy="true"]')) {
      dialog.close();
    }
  }

  /** ダイアログを閉じた後、登録を開始した選択欄にフォーカスを戻す。 */
  focusSelectLater(selectId) {
    if (!selectId) {
      return;
    }
    this.window.requestAnimationFrame(() => this.document.querySelector(`#${selectId}`)?.focus());
  }

  /** 未選択をnull、それ以外を数値にする。最終的な型・範囲検証はAPIが担当する。 */
  toNullableId(value) {
    return value === "" || value === null ? null : Number(value);
  }

  /** 空白だけの任意テキストをnullへそろえる。 */
  toNullableText(value) {
    const trimmed = value.trim();
    return trimmed === "" ? null : trimmed;
  }

  /** 空白除去済みの必須入力を確認し、失敗時は対象欄に理由を表示する。 */
  validateRequiredText(value, input, message) {
    input.setCustomValidity(value ? "" : message);
    if (!value) {
      input.reportValidity();
      input.focus();
      return false;
    }
    return true;
  }

  /** 送信中の入力と閉じる操作を無効化する。呼び出し側のfinallyで解除する。 */
  setFormBusy(form, busy) {
    form.setAttribute("aria-busy", String(busy));
    form.querySelectorAll("input, textarea, select, button").forEach((control) => {
      control.disabled = busy;
    });
    form
      .closest("dialog")
      ?.querySelectorAll("[data-close-dialog]")
      .forEach((button) => {
        button.disabled = busy;
      });
  }

  /** 一覧の取得中表示と再取得ボタンの状態をそろえる。 */
  setTaskListLoading(loading) {
    this.elements.loadingState.hidden = !loading;
    this.elements.refreshTasks.disabled = loading;
    this.elements.taskList.setAttribute("aria-busy", String(loading));
  }

  /** 対象カードの操作を一時停止する。再描画でカードが消えていれば何もしない。 */
  setTaskCardBusy(taskId, busy) {
    const card = this.elements.taskList.querySelector(`[data-task-id="${taskId}"]`);
    if (!card) {
      return;
    }

    card.setAttribute("aria-busy", String(busy));
    card.querySelectorAll("input, button").forEach((control) => {
      control.disabled = busy;
    });
  }

  /** 現在の検索条件を表示用の文字列にする。 */
  buildFilterLabel() {
    const statusLabels = {
      all: "すべての状態",
      open: "未完了",
      done: "完了",
    };
    const category = this.state.categories.find(
      (item) => item.id === this.state.filters.categoryId,
    );
    return category
      ? `${statusLabels[this.state.filters.status]}・${category.name}`
      : statusLabels[this.state.filters.status];
  }

  /** APIの日時を表示形式にする。解釈できない値は元の文字列を表示する。 */
  formatDateTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return new Intl.DateTimeFormat("ja-JP", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  /** 操作中のダイアログ、または一覧へ通知を出す。エラーは残し、成功通知のみ時間で消す。 */
  showFeedback(message, type = "success") {
    this.window.clearTimeout(this.feedbackTimer);
    const activeDialog = [...this.document.querySelectorAll("dialog[open]")].at(-1);
    const feedback =
      activeDialog?.querySelector("[data-dialog-feedback]") ?? this.elements.feedback;
    this.document.querySelectorAll(".feedback").forEach((item) => {
      item.hidden = item !== feedback;
    });
    feedback.textContent = message;
    feedback.classList.remove("feedback--success", "feedback--error");
    feedback.classList.add(`feedback--${type}`);
    feedback.hidden = false;
    if (type !== "error") {
      this.feedbackTimer = this.window.setTimeout(() => {
        feedback.hidden = true;
      }, 5000);
    }
  }
}

// HTML解析後、ブラウザのdocumentが使えるときに画面を初期化する。
if (typeof document !== "undefined") {
  const app = new TaskApp();
  app.initialize();
}
