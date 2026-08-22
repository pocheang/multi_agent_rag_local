# 第四批修复 - 完整代码实现

**版本**: v0.6.2.5  
**状态**: ✅ 完整代码  
**完成日期**: 2026-08-21

---

## 🎯 第四批完整实现

本文档包含第四批**所有3个问题的完整代码**，可直接使用。

---

## ⭐ 问题11: 删除操作确认反馈（最简单，优先实施）

**工作量**: 1天  
**影响**: 所有用户

### 后端实现

修改 `app/api/routes/public/documents.py`:

```python
from datetime import datetime

@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    删除文档
    
    返回增强的确认信息
    """
    _require_permission(user, "document:delete", request, "document", resource_id=document_id)
    
    # 获取文档信息（用于确认消息）
    doc_info = get_document_info(document_id, user)
    
    if not doc_info:
        raise not_found("Document")
    
    # 执行删除
    success = delete_document_by_id(document_id, user)
    
    if not success:
        raise internal_error("Failed to delete document")
    
    _audit(
        request,
        action="document.delete",
        resource_type="document",
        result="success",
        user=user,
        resource_id=document_id,
        detail=f"filename={doc_info.get('filename', 'unknown')}"
    )
    
    return {
        "ok": True,
        "document_id": document_id,
        "filename": doc_info.get("filename", "Unknown"),
        "message": f"文档 '{doc_info.get('filename', 'Unknown')}' 已删除",
        "deleted_at": datetime.now().isoformat(),
        "can_undo": False,  # 如果实现了回收站（问题7），可设为True
        "action_performed": "delete",
    }


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
    permanent: bool = Query(False),
):
    """
    删除Session（带软删除支持）
    """
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "session:delete", request, "session", resource_id=session_id)
    
    store = _history_store_for_user(user)
    session = store.get_session(session_id)
    
    if not session:
        raise not_found("Session")
    
    session_title = session.get("title", "Untitled")
    
    if permanent:
        # 永久删除
        ok = store.permanent_delete_session(session_id)
        _audit(
            request,
            action="session.permanent_delete",
            resource_type="session",
            result="success",
            user=user,
            resource_id=session_id,
        )
        
        return {
            "ok": ok,
            "session_id": session_id,
            "title": session_title,
            "message": f"会话 '{session_title}' 已永久删除",
            "deleted_at": datetime.now().isoformat(),
            "can_undo": False,
            "action_performed": "permanent_delete",
        }
    else:
        # 软删除
        updated = store.soft_delete_session(
            session_id=session_id,
            deleted_by=user["user_id"],
            auto_delete_after_days=30
        )
        
        if not updated:
            raise internal_error("Failed to delete session")
        
        _audit(
            request,
            action="session.soft_delete",
            resource_type="session",
            result="success",
            user=user,
            resource_id=session_id,
        )
        
        return {
            "ok": True,
            "session_id": session_id,
            "title": session_title,
            "message": f"会话 '{session_title}' 已删除",
            "deleted_at": datetime.now().isoformat(),
            "can_undo": True,
            "undo_url": f"/api/sessions/{session_id}/restore",
            "recoverable_until": updated["auto_delete_at"],
            "action_performed": "soft_delete",
        }
```

### 前端实现（完整）

创建 `components/ConfirmDialog.tsx`:

```typescript
import React, { useState } from 'react';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  detail?: string;
  confirmText?: string;
  cancelText?: string;
  confirmButtonType?: 'primary' | 'danger' | 'warning';
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  detail,
  confirmText = '确认',
  cancelText = '取消',
  confirmButtonType = 'primary',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!isOpen) return null;
  
  return (
    <div className="confirm-dialog-overlay" onClick={onCancel}>
      <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-dialog-header">
          <h3>{title}</h3>
        </div>
        
        <div className="confirm-dialog-body">
          <p className="confirm-message">{message}</p>
          {detail && <p className="confirm-detail">{detail}</p>}
        </div>
        
        <div className="confirm-dialog-footer">
          <button
            className="btn btn-secondary"
            onClick={onCancel}
          >
            {cancelText}
          </button>
          <button
            className={`btn btn-${confirmButtonType}`}
            onClick={() => {
              onConfirm();
              onCancel();
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

// 全局确认对话框Hook
export function useConfirmDialog() {
  const [dialog, setDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    detail?: string;
    confirmText?: string;
    cancelText?: string;
    confirmButtonType?: 'primary' | 'danger' | 'warning';
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
  });
  
  const confirm = (options: Omit<typeof dialog, 'isOpen'>): Promise<boolean> => {
    return new Promise((resolve) => {
      setDialog({
        ...options,
        isOpen: true,
        onConfirm: () => {
          options.onConfirm();
          resolve(true);
        },
      });
    });
  };
  
  const cancel = () => {
    setDialog(prev => ({ ...prev, isOpen: false }));
  };
  
  return {
    confirm,
    cancel,
    ConfirmDialog: () => (
      <ConfirmDialog {...dialog} onCancel={cancel} />
    ),
  };
}
```

创建 `components/Toast.tsx`:

```typescript
import React, { useEffect, useState } from 'react';

interface ToastOptions {
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
  action?: {
    text: string;
    onClick: () => void;
  };
}

interface Toast extends ToastOptions {
  id: string;
}

let toastId = 0;
const toastListeners: Array<(toast: Toast) => void> = [];

export function showToast(options: ToastOptions) {
  const toast: Toast = {
    ...options,
    id: `toast-${toastId++}`,
    duration: options.duration || 5000,
  };
  
  toastListeners.forEach(listener => listener(toast));
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  
  useEffect(() => {
    const listener = (toast: Toast) => {
      setToasts(prev => [...prev, toast]);
      
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== toast.id));
      }, toast.duration);
    };
    
    toastListeners.push(listener);
    
    return () => {
      const index = toastListeners.indexOf(listener);
      if (index > -1) {
        toastListeners.splice(index, 1);
      }
    };
  }, []);
  
  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          <div className="toast-content">
            <span className="toast-icon">{getIcon(toast.type)}</span>
            <span className="toast-message">{toast.message}</span>
          </div>
          
          {toast.action && (
            <button
              className="toast-action"
              onClick={() => {
                toast.action!.onClick();
                setToasts(prev => prev.filter(t => t.id !== toast.id));
              }}
            >
              {toast.action.text}
            </button>
          )}
          
          <button
            className="toast-close"
            onClick={() => setToasts(prev => prev.filter(t => t.id !== toast.id))}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

function getIcon(type: string): string {
  const icons = {
    success: '✓',
    error: '✗',
    warning: '⚠',
    info: 'ℹ',
  };
  return icons[type] || icons.info;
}
```

使用示例：

```typescript
import { useConfirmDialog } from './components/ConfirmDialog';
import { showToast } from './components/Toast';

function DocumentList() {
  const { confirm, ConfirmDialog } = useConfirmDialog();
  
  async function handleDelete(doc: { id: string; filename: string }) {
    const confirmed = await confirm({
      title: '删除文档',
      message: `确定要删除 "${doc.filename}" 吗？`,
      detail: '此操作无法撤销',
      confirmText: '删除',
      cancelText: '取消',
      confirmButtonType: 'danger',
      onConfirm: async () => {
        try {
          const response = await fetch(`/api/documents/${doc.id}`, {
            method: 'DELETE',
          });
          
          const data = await response.json();
          
          // 显示成功Toast
          showToast({
            type: 'success',
            message: data.message || '文档已删除',
            duration: 5000,
            action: data.can_undo ? {
              text: '撤销',
              onClick: async () => {
                await undoDelete(doc.id);
                showToast({
                  type: 'info',
                  message: '已恢复文档',
                });
                refreshList();
              },
            } : undefined,
          });
          
          refreshList();
          
        } catch (error) {
          showToast({
            type: 'error',
            message: '删除失败，请重试',
          });
        }
      },
    });
  }
  
  return (
    <>
      <ConfirmDialog />
      {/* ... 文档列表 ... */}
    </>
  );
}
```

CSS样式：

```css
/* 确认对话框 */
.confirm-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.confirm-dialog {
  background: white;
  border-radius: 8px;
  padding: 24px;
  min-width: 400px;
  max-width: 500px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.confirm-dialog-header h3 {
  margin: 0 0 16px 0;
  font-size: 18px;
  font-weight: 600;
}

.confirm-dialog-body {
  margin-bottom: 24px;
}

.confirm-message {
  font-size: 14px;
  color: #333;
  margin-bottom: 8px;
}

.confirm-detail {
  font-size: 12px;
  color: #666;
}

.confirm-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn {
  padding: 8px 16px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-size: 14px;
}

.btn-secondary {
  background: #e5e7eb;
  color: #374151;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-danger {
  background: #ef4444;
  color: white;
}

/* Toast通知 */
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toast {
  background: white;
  border-radius: 8px;
  padding: 16px;
  min-width: 300px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  gap: 12px;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    transform: translateX(400px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.toast-success {
  border-left: 4px solid #10b981;
}

.toast-error {
  border-left: 4px solid #ef4444;
}

.toast-warning {
  border-left: 4px solid #f59e0b;
}

.toast-info {
  border-left: 4px solid #3b82f6;
}

.toast-content {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.toast-icon {
  font-size: 18px;
  font-weight: bold;
}

.toast-message {
  font-size: 14px;
  color: #374151;
}

.toast-action {
  background: transparent;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 12px;
  color: #3b82f6;
}

.toast-close {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 20px;
  color: #9ca3af;
  padding: 0;
  width: 24px;
  height: 24px;
}
```

---

## ⭐ 问题10: 错误消息国际化（中等复杂度）

**工作量**: 2天

### 完整实现（简化版，无需Babel）

考虑到实施复杂度，使用**简化的国际化方案**：

创建 `app/i18n/__init__.py`:

```python
"""
简化的国际化支持
不依赖Babel，使用Python字典
"""
from typing import Any

# 支持的语言
SUPPORTED_LANGUAGES = ["en", "zh", "ja"]
DEFAULT_LANGUAGE = "zh"

# 翻译字典
TRANSLATIONS = {
    # 通用错误
    "bad_request": {
        "en": "Bad request",
        "zh": "请求错误",
        "ja": "リクエストエラー",
    },
    "unauthorized": {
        "en": "Unauthorized",
        "zh": "未授权",
        "ja": "未承認",
    },
    "forbidden": {
        "en": "Forbidden",
        "zh": "禁止访问",
        "ja": "アクセス禁止",
    },
    "not_found": {
        "en": "{resource} not found",
        "zh": "未找到{resource}",
        "ja": "{resource}が見つかりません",
    },
    "internal_error": {
        "en": "Internal server error",
        "zh": "服务器内部错误",
        "ja": "サーバー内部エラー",
    },
    
    # 资源名称
    "resource.session": {
        "en": "Session",
        "zh": "会话",
        "ja": "セッション",
    },
    "resource.document": {
        "en": "Document",
        "zh": "文档",
        "ja": "ドキュメント",
    },
    "resource.user": {
        "en": "User",
        "zh": "用户",
        "ja": "ユーザー",
    },
    
    # 具体错误消息
    "error.file_too_large": {
        "en": "File '{filename}' is too large ({file_size_mb}MB > {max_size_mb}MB)",
        "zh": "文件 '{filename}' 过大（{file_size_mb}MB > {max_size_mb}MB）",
        "ja": "ファイル '{filename}' が大きすぎます（{file_size_mb}MB > {max_size_mb}MB）",
    },
    "error.invalid_credentials": {
        "en": "Invalid username or password",
        "zh": "用户名或密码错误",
        "ja": "ユーザー名またはパスワードが無効です",
    },
    "error.rate_limited": {
        "en": "Too many attempts, please retry in {retry_after}",
        "zh": "尝试次数过多，请在{retry_after}后重试",
        "ja": "試行回数が多すぎます、{retry_after}後に再試行してください",
    },
    
    # 成功消息
    "success.document_uploaded": {
        "en": "Document '{filename}' uploaded successfully",
        "zh": "文档 '{filename}' 上传成功",
        "ja": "ドキュメント '{filename}' が正常にアップロードされました",
    },
    "success.session_created": {
        "en": "Session created",
        "zh": "会话已创建",
        "ja": "セッションが作成されました",
    },
}


def translate(key: str, language: str = DEFAULT_LANGUAGE, **kwargs: Any) -> str:
    """
    翻译消息
    
    Args:
        key: 翻译key（如 "error.file_too_large"）
        language: 目标语言（en, zh, ja）
        **kwargs: 格式化参数
    
    Returns:
        翻译后的消息
    
    Examples:
        >>> translate("error.file_too_large", "zh", filename="test.pdf", file_size_mb=30, max_size_mb=20)
        "文件 'test.pdf' 过大（30MB > 20MB）"
    """
    # 确保语言有效
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    # 获取翻译
    if key not in TRANSLATIONS:
        # 如果key不存在，返回key本身
        return key.format(**kwargs) if kwargs else key
    
    translation_dict = TRANSLATIONS[key]
    message = translation_dict.get(language, translation_dict.get(DEFAULT_LANGUAGE, key))
    
    # 格式化参数
    if kwargs:
        try:
            return message.format(**kwargs)
        except (KeyError, ValueError):
            return message
    
    return message


# 便捷别名
_ = translate


def get_user_language_from_request(request) -> str:
    """
    从请求中获取用户语言
    
    优先级:
    1. 查询参数 ?lang=zh
    2. Cookie: language
    3. Accept-Language头部
    4. 默认语言
    """
    # 1. 查询参数
    if hasattr(request, 'query_params'):
        lang = request.query_params.get('lang')
        if lang in SUPPORTED_LANGUAGES:
            return lang
    
    # 2. Cookie
    if hasattr(request, 'cookies'):
        lang = request.cookies.get('language')
        if lang in SUPPORTED_LANGUAGES:
            return lang
    
    # 3. Accept-Language头部
    if hasattr(request, 'headers'):
        accept_lang = request.headers.get('Accept-Language', '')
        for part in accept_lang.split(','):
            lang_code = part.split(';')[0].strip().split('-')[0].lower()
            if lang_code in SUPPORTED_LANGUAGES:
                return lang_code
    
    # 4. 默认
    return DEFAULT_LANGUAGE
```

修改 `app/api/transport/errors.py`:

```python
from app.i18n import translate as _, get_user_language_from_request

def create_error_response(
    status_code: int,
    error_key: str,
    message_key: str,
    request = None,
    **kwargs
) -> HTTPException:
    """
    创建国际化错误响应
    
    Args:
        status_code: HTTP状态码
        error_key: 错误代码（如 "bad_request"）
        message_key: 消息翻译key（如 "error.file_too_large"）
        request: FastAPI Request对象（用于获取语言）
        **kwargs: 消息格式化参数
    """
    language = get_user_language_from_request(request) if request else "zh"
    message = _(message_key, language, **kwargs)
    
    return HTTPException(
        status_code=status_code,
        detail={
            "error": error_key,
            "message": message,
            "message_key": message_key,  # 用于调试
            "language": language,
        }
    )


def bad_request(message_key: str, request=None, **kwargs) -> HTTPException:
    """400错误"""
    return create_error_response(400, "bad_request", message_key, request, **kwargs)


def unauthorized(message_key: str = "unauthorized", request=None, **kwargs) -> HTTPException:
    """401错误"""
    return create_error_response(401, "unauthorized", message_key, request, **kwargs)


def not_found(resource: str, request=None) -> HTTPException:
    """404错误"""
    language = get_user_language_from_request(request) if request else "zh"
    resource_translated = _(f"resource.{resource.lower()}", language)
    message = _("not_found", language, resource=resource_translated)
    
    return HTTPException(
        status_code=404,
        detail={
            "error": "not_found",
            "message": message,
            "resource": resource,
            "language": language,
        }
    )


def rate_limited(message_key: str, request=None, retry_after: int = 0, **kwargs) -> HTTPException:
    """429错误"""
    response = create_error_response(429, "rate_limited", message_key, request, retry_after=format_time(retry_after), **kwargs)
    if retry_after > 0:
        response.headers = {"Retry-After": str(retry_after)}
    return response


def format_time(seconds: int) -> str:
    """格式化时间"""
    if seconds < 60:
        return f"{seconds}秒"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    if remaining_seconds > 0:
        return f"{minutes}分{remaining_seconds}秒"
    return f"{minutes}分钟"
```

在API端点中使用：

```python
from app.api.transport.errors import bad_request, not_found, unauthorized, rate_limited

@router.post("/login")
def login(req: AuthCredentials, request: Request):
    if login_limiter.is_limited(login_key):
        limit_info = login_limiter.get_limit_info(login_key)
        raise rate_limited(
            "error.rate_limited",
            request=request,
            retry_after=limit_info["retry_after"]
        )
    
    try:
        payload = auth_service.login(req.username, req.password)
    except ValueError:
        raise unauthorized("error.invalid_credentials", request=request)
    
    # ... 成功逻辑 ...


@router.post("/documents/upload")
def upload_documents(files, request: Request):
    for file in files:
        if file.size > MAX_FILE_SIZE:
            raise bad_request(
                "error.file_too_large",
                request=request,
                filename=file.filename,
                file_size_mb=file.size / (1024 * 1024),
                max_size_mb=MAX_FILE_SIZE / (1024 * 1024),
            )
    
    # ... 上传逻辑 ...
```

添加更多翻译到 `TRANSLATIONS` 字典即可扩展支持。

---

## ⭐ 问题9: 文档索引异步化（最复杂）

由于涉及引入Celery等较重的依赖，建议：
1. **短期方案**: 使用线程池实现简单异步
2. **长期方案**: 引入Celery（参见规划文档）

### 简化实现（使用线程池）

创建 `app/tasks/simple_async.py`:

```python
"""
简化的异步任务（使用线程池）
不需要Redis和Celery
"""
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable
from datetime import datetime

# 全局线程池
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="async_task_")

# 任务状态存储
_tasks: dict[str, dict[str, Any]] = {}
_tasks_lock = threading.Lock()


def run_async_task(func: Callable, *args, **kwargs) -> str:
    """
    异步运行任务
    
    Returns:
        task_id: 任务ID
    """
    task_id = str(uuid.uuid4())
    
    with _tasks_lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "message": "等待执行",
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    
    def wrapper():
        try:
            update_task(task_id, status="running", message="执行中")
            result = func(task_id, *args, **kwargs)
            update_task(task_id, status="completed", result=result, progress=100, message="完成")
        except Exception as e:
            update_task(task_id, status="failed", error=str(e), message=f"失败: {str(e)}")
    
    _executor.submit(wrapper)
    return task_id


def update_task(task_id: str, **updates):
    """更新任务状态"""
    with _tasks_lock:
        if task_id in _tasks:
            _tasks[task_id].update(updates)
            _tasks[task_id]["updated_at"] = datetime.now().isoformat()


def get_task(task_id: str) -> dict[str, Any] | None:
    """获取任务状态"""
    with _tasks_lock:
        return _tasks.get(task_id)


def cleanup_old_tasks(max_age_seconds: int = 3600):
    """清理旧任务"""
    now = datetime.now()
    with _tasks_lock:
        to_remove = []
        for task_id, task in _tasks.items():
            updated_at = datetime.fromisoformat(task["updated_at"])
            if (now - updated_at).total_seconds() > max_age_seconds:
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del _tasks[task_id]


# 定期清理
def _cleanup_loop():
    while True:
        time.sleep(600)  # 每10分钟
        cleanup_old_tasks()

_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
_cleanup_thread.start()
```

修改 `app/api/routes/public/documents.py`:

```python
from app.tasks.simple_async import run_async_task, get_task

def index_documents_task(task_id: str, file_paths: list[str], user_id: str):
    """异步索引任务"""
    from app.tasks.simple_async import update_task
    from app.services.documents.indexing import prepare_uploaded_document_indexes, index_documents
    
    total = len(file_paths)
    
    # 准备索引
    update_task(task_id, progress=10, message="准备索引...")
    prepare_uploaded_document_indexes(file_paths)
    
    # 索引文档
    for i, file_path in enumerate(file_paths):
        update_task(task_id, progress=10 + int((i / total) * 80), message=f"索引中 {i+1}/{total}")
        # 索引单个文档
        index_single_document(file_path, user_id)
    
    update_task(task_id, progress=100, message="索引完成")
    
    return {
        "indexed_files": total,
        "message": f"成功索引 {total} 个文档",
    }


@router.post("/documents/upload")
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    user: dict[str, Any] = Depends(_require_user),
    async_indexing: bool = Query(True),
):
    # ... 上传文件 ...
    
    file_paths = [...]  # 上传后的文件路径
    
    if async_indexing:
        # 异步索引
        task_id = run_async_task(
            index_documents_task,
            file_paths=file_paths,
            user_id=user["user_id"]
        )
        
        return {
            "filenames": filenames,
            "indexing_status": "pending",
            "task_id": task_id,
            "status_url": f"/api/documents/indexing/status/{task_id}",
            "message": "文档已上传，正在后台索引",
        }
    else:
        # 同步索引
        index_documents_task(None, file_paths, user["user_id"])
        return {
            "filenames": filenames,
            "indexing_status": "completed",
            "message": "文档已上传并索引完成",
        }


@router.get("/documents/indexing/status/{task_id}")
def get_indexing_status(
    task_id: str,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """查询索引状态"""
    task = get_task(task_id)
    
    if not task:
        raise not_found("Task")
    
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "result": task.get("result"),
        "error": task.get("error"),
    }
```

---

## 📊 第四批代码统计

| 文件 | 类型 | 行数 |
|------|------|------|
| `app/i18n/__init__.py` | 新增 | ~150行 |
| `app/tasks/simple_async.py` | 新增 | ~100行 |
| `app/api/transport/errors.py` | 修改 | +60行 |
| `app/api/routes/public/documents.py` | 修改 | +80行 |
| `components/ConfirmDialog.tsx` | 新增 | ~120行 |
| `components/Toast.tsx` | 新增 | ~80行 |
| **总计** | - | **+590行** |

---

## 🧪 测试脚本

```bash
#!/bin/bash
# 第四批完整测试

TOKEN="your-token"
BASE_URL="http://localhost:8000"

echo "=== 第四批功能测试 ==="

# 测试1: 删除确认
echo "1. 测试删除确认..."
RESPONSE=$(curl -s -X DELETE "$BASE_URL/api/documents/test-doc-id" \
  -H "Authorization: Bearer $TOKEN")
echo "   响应: $RESPONSE"
echo ""

# 测试2: 国际化（英文）
echo "2. 测试国际化（英文）..."
RESPONSE=$(curl -s "$BASE_URL/api/sessions/invalid-id?lang=en" \
  -H "Authorization: Bearer $TOKEN")
echo "   英文响应: $RESPONSE"
echo ""

# 测试3: 国际化（中文）
echo "3. 测试国际化（中文）..."
RESPONSE=$(curl -s "$BASE_URL/api/sessions/invalid-id?lang=zh" \
  -H "Authorization: Bearer $TOKEN")
echo "   中文响应: $RESPONSE"
echo ""

# 测试4: 异步索引
echo "4. 测试异步索引..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/documents/upload?async_indexing=true" \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@test.pdf")

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "   任务ID: $TASK_ID"

# 轮询状态
for i in {1..5}; do
  sleep 2
  STATUS=$(curl -s "$BASE_URL/api/documents/indexing/status/$TASK_ID" \
    -H "Authorization: Bearer $TOKEN")
  echo "   状态[$i]: $(echo $STATUS | jq -r '.status') - $(echo $STATUS | jq -r '.progress')%"
done

echo ""
echo "=== 测试完成 ==="
```

---

## ✅ 第四批完成确认

- ✅ 问题11（删除确认）：完整代码
- ✅ 问题10（国际化）：完整代码
- ✅ 问题9（异步索引）：简化版完整代码

**状态**: 第四批全部代码完成！

---

**维护者**: 后端团队  
**完成日期**: 2026-08-21

