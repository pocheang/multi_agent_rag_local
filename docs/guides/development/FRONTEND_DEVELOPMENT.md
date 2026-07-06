# 前端开发 (Frontend Development)

本文档介绍 QueryMind（智询） 系统的前端开发指南，包括 React 组件开发、状态管理和 API 集成。

## 目录

- [快速参考](#快速参考)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [开发环境](#开发环境)
- [组件开发](#组件开发)
- [状态管理](#状态管理)
- [API 集成](#api-集成)
- [路由管理](#路由管理)
- [样式系统](#样式系统)
- [国际化](#国际化)
- [测试](#测试)

---

## 快速参考

### 常用命令速查

```bash
# 安装依赖
cd frontend
npm install

# 开发模式（热更新）
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview

# 提取关键 CSS
npm run extract-critical

# 代码格式化
npm run format

# 代码检查
npm run lint

# 类型检查
npm run type-check
```

### 组件速查

| 组件类型 | 位置 | 示例 |
|---------|------|------|
| **页面组件** | `src/pages/` | `ChatPage.tsx`, `AdminPage.tsx` |
| **UI 组件** | `src/components/` | `AuthInput.tsx`, `CodeBlock.tsx` |
| **布局组件** | `src/components/` | `ThemeToggle.tsx`, `LanguageToggle.tsx` |
| **工具组件** | `src/components/` | `ConfirmDialog.tsx`, `KeyboardHelp.tsx` |

### API 调用速查

```typescript
// 使用 authApi
import { authApi } from "@/lib/api";

// 登录
const user = await authApi.login(username, password);

// 获取当前用户
const user = await authApi.getCurrentUser();

// 登出
await authApi.logout();
```

```typescript
// 使用 queryApi
import { queryApi } from "@/lib/api";

// 发送查询
const result = await queryApi.query(sessionId, question);

// 流式查询
for await (const chunk of queryApi.queryStream(sessionId, question)) {
  console.log(chunk);
}
```

### 路由速查

| 路径 | 组件 | 权限 | 说明 |
|------|------|------|------|
| `/app/login` | LoginPage | 公开 | 登录页 |
| `/app` | ChatPage | 需认证 | 聊天主页 |
| `/app/admin` | AdminPage | 需管理员 | 管理面板 |
| `/app/analytics` | AnalyticsPage | 需认证 | 分析页面 |
| `/app/architecture` | ArchitecturePage | 需认证 | 架构可视化 |
| `/app/profile` | ProfilePage | 需认证 | 用户资料 |

### TypeScript 类型速查

```typescript
// 用户类型
interface AuthUser {
  user_id: string;
  username: string;
  role: "user" | "admin";
}

// 查询请求
interface QueryRequest {
  session_id: string;
  question: string;
  strategy?: "fast" | "balanced" | "deep";
}

// 查询响应
interface QueryResponse {
  answer: string;
  sources: string[];
  metadata: {
    duration_ms: number;
    tokens_used: number;
  };
}
```

### 环境变量速查

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000

# .env.production
VITE_API_BASE_URL=https://api.example.com
VITE_WS_BASE_URL=wss://api.example.com
```

---

## 技术栈

QueryMind（智询） 的前端采用现代化的 React 技术栈，强调类型安全、开发效率和用户体验。

### 核心框架

本项目使用 React 18 作为核心 UI 框架，配合 TypeScript 提供完整的类型安全保障。React 18 引入的并发特性和自动批处理提升了应用性能，而 TypeScript 则在编译时就能发现潜在的类型错误，大大降低了运行时错误的可能性。

构建工具选择了 Vite，相比传统的 Webpack，Vite 利用浏览器原生 ES 模块支持，实现了极快的冷启动和热更新速度。在开发过程中，代码修改后几乎能立即看到效果，显著提升了开发体验。

路由管理使用 React Router v6，它提供了声明式的路由配置方式，支持嵌套路由、懒加载和路由守卫等高级特性。相比前一版本，v6 的 API 更简洁，性能也有所提升。

| 技术 | 版本 | 用途 |
|------|------|------|
| **React** | 18.3+ | UI 框架 |
| **TypeScript** | 5.9+ | 类型安全 |
| **Vite** | 6.4+ | 构建工具 |
| **React Router** | 6.30+ | 路由管理 |

### UI 和样式

样式系统采用 CSS Modules，每个组件的样式都被作用域隔离，避免了全局样式污染的问题。这种方式既保持了 CSS 的简单性，又获得了模块化的好处。

为了方便条件类名的组合，使用了 clsx 库。它提供了简洁的 API 来根据条件动态组合多个类名，在实现响应式设计和状态相关的样式时特别有用。

markdown 内容的渲染使用 react-markdown，它能将服务端返回的 Markdown 格式的答案安全地渲染为 HTML，同时支持 GFM（GitHub Flavored Markdown）扩展语法，如表格、任务列表等。

数据可视化方面，recharts 提供了丰富的图表组件，用于展示查询分析数据；reactflow 则用于渲染系统架构图和工作流可视化。

| 技术 | 用途 |
|------|------|
| **CSS Modules** | 模块化样式 |
| **clsx** | 条件类名 |
| **react-markdown** | Markdown 渲染 |
| **recharts** | 图表可视化 |
| **reactflow** | 流程图 |

### 国际化和工具

国际化使用 react-i18next，它是 i18next 的 React 绑定库。i18next 是一个功能强大的国际化框架，支持多语言、命名空间、插值、复数等特性。项目目前支持中英文双语，可以根据用户偏好自动切换。

| 技术 | 用途 |
|------|------|
| **react-i18next** | 国际化 |
| **i18next** | i18n 核心 |

---

## 项目结构

前端代码组织遵循功能分离和关注点分离的原则，每个目录都有明确的职责。

**组件目录** (`components/`) 存放可复用的 UI 组件。这些组件通常是无状态的或只包含自身的局部状态，可以在多个页面中使用。例如 `AuthInput` 用于表单输入，`CodeBlock` 用于代码高亮显示，`ThemeToggle` 用于主题切换。

**页面目录** (`pages/`) 包含路由级别的页面组件。每个页面通常对应一个路由路径，负责组合多个 UI 组件并处理页面级的业务逻辑。例如 `ChatPage` 是聊天主页，`AdminPage` 是管理面板，`LoginPage` 是登录页。

**工具库目录** (`lib/`) 存放通用的工具函数和服务。`api.ts` 封装了所有的 API 调用，`theme.ts` 处理主题切换逻辑，`utils.ts` 包含各种辅助函数。这些工具不依赖于特定的组件，可以在整个应用中使用。

**类型目录** (`types/`) 定义 TypeScript 类型和接口。将类型定义集中管理有助于保持类型的一致性，也方便在多个文件中共享类型定义。

**国际化目录** (`i18n/`) 包含国际化配置和翻译文件。翻译文件按语言组织，每种语言一个 JSON 文件。配置文件负责初始化 i18next 并加载翻译资源。

```
frontend/
├── src/
│   ├── components/          # UI 组件
│   │   ├── AuthInput.tsx
│   │   ├── CodeBlock.tsx
│   │   ├── ThemeToggle.tsx
│   │   └── ...
│   │
│   ├── pages/              # 页面组件
│   │   ├── ChatPage.tsx
│   │   ├── AdminPage.tsx
│   │   └── LoginPage.tsx
│   │
│   ├── lib/                # 工具库
│   │   ├── api.ts          # API 客户端
│   │   ├── theme.ts        # 主题管理
│   │   └── utils.ts        # 工具函数
│   │
│   ├── types/              # TypeScript 类型
│   │   └── api.ts
│   │
│   ├── i18n/               # 国际化
│   │   ├── config.ts
│   │   └── locales/
│   │       ├── en.json
│   │       └── zh.json
│   │
│   ├── App.tsx             # 应用根组件
│   ├── main.tsx            # 应用入口
│   └── styles.css          # 全局样式
│
├── public/                 # 静态资源
├── package.json            # 依赖配置
├── tsconfig.json           # TypeScript 配置
└── vite.config.mjs        # Vite 配置
```

---

## 开发环境

### 开发服务器

Vite 开发服务器提供了快速的热模块替换（HMR）功能。当你修改代码时，浏览器会在几乎不刷新页面的情况下更新修改的模块，保留了组件的状态。这对于调试特定状态下的 UI 特别有用。

开发服务器默认运行在 5173 端口，可以通过 Vite 配置文件修改。配置文件中还可以设置代理，将前端的 API 请求转发到后端服务器，避免跨域问题。

### 初始化项目

首先需要安装所有依赖包。npm install 会根据 package.json 中的依赖列表下载所需的包到 node_modules 目录。这个过程可能需要几分钟，取决于网络速度。

安装完成后，使用 npm run dev 启动开发服务器。Vite 会编译源代码并启动一个本地服务器。你会在终端看到服务器地址，通常是 http://localhost:5173。在浏览器中打开这个地址就能看到应用界面。

开发模式下，代码修改会立即反映到浏览器中，无需手动刷新页面。这大大提高了开发效率。

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev

# 4. 访问
# http://localhost:5173/app
```

### 开发服务器配置

Vite 配置文件使用 JavaScript 编写，支持插件和各种自定义选项。

**路径别名** (`@`) 配置让你可以使用绝对路径导入模块，避免相对路径的层级问题。例如 `import { api } from "@/lib/api"` 比 `import { api } from "../../../lib/api"` 更清晰。

**代理配置** 将以 `/api` 开头的请求转发到后端服务器（默认 localhost:8000）。这样前端代码可以直接调用 `/api/query` 而不用关心后端服务器的具体地址，也避免了跨域问题。

**vite.config.mjs**:
```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

---

## 组件开发

### 组件设计原则

React 组件应该遵循单一职责原则，每个组件只做一件事。这使得组件更容易理解、测试和复用。

函数组件配合 Hooks 是 React 的推荐方式。相比类组件，函数组件更简洁，Hooks 提供了更灵活的状态管理和副作用处理方式。

TypeScript 类型定义是必需的。为组件的 props 定义接口不仅能提供类型检查，还能作为组件的文档，让其他开发者一眼就能看出组件接受哪些参数。

### 函数组件模板

一个标准的函数组件包含以下几部分：

1. **导入语句** - 引入需要的 React Hooks、样式文件和其他依赖
2. **Props 接口定义** - 使用 TypeScript 接口定义组件接受的属性
3. **组件函数** - 使用函数声明，接受 props 作为参数
4. **状态和副作用** - 使用 useState、useEffect 等 Hooks
5. **事件处理函数** - 定义组件内部的交互逻辑
6. **JSX 返回** - 返回组件的 UI 结构

Props 接口中，必需的属性直接声明类型，可选属性使用 `?` 标记，并可以提供默认值。回调函数使用 `onXxx` 命名约定，并标记为可选。

```typescript
import { useState } from "react";
import styles from "./MyComponent.module.css";

interface MyComponentProps {
  title: string;
  count?: number;
  onUpdate?: (value: number) => void;
}

export function MyComponent({ 
  title, 
  count = 0, 
  onUpdate 
}: MyComponentProps) {
  const [value, setValue] = useState(count);

  const handleClick = () => {
    const newValue = value + 1;
    setValue(newValue);
    onUpdate?.(newValue);
  };

  return (
    <div className={styles.container}>
      <h2>{title}</h2>
      <p>Count: {value}</p>
      <button onClick={handleClick}>Increment</button>
    </div>
  );
}
```

### Hooks 使用

React Hooks 是函数组件中管理状态和副作用的主要方式。

**useState** 用于管理组件的本地状态。它返回一个状态值和一个更新函数。状态更新是异步的，React 会批量处理多个状态更新以提高性能。

**useEffect** 用于处理副作用，如数据获取、订阅或手动修改 DOM。它在组件渲染后执行，可以返回一个清理函数在组件卸载时执行。依赖数组控制 effect 何时重新执行。

**useCallback** 缓存函数引用，避免每次渲染时创建新的函数实例。这在将回调传递给子组件时特别有用，可以避免不必要的子组件重渲染。

**useMemo** 缓存计算结果。如果计算开销大，使用 useMemo 可以避免每次渲染时重新计算。

自定义 Hook 是封装可复用逻辑的好方法。它本质上是一个以 "use" 开头的函数，可以调用其他 Hooks。例如 useAuth 封装了用户认证相关的逻辑，可以在多个组件中使用。

**useState - 状态管理**:
```typescript
const [count, setCount] = useState(0);
const [user, setUser] = useState<User | null>(null);
```

**useEffect - 副作用**:
```typescript
useEffect(() => {
  // 组件挂载时执行
  fetchData();
  
  // 清理函数
  return () => {
    cleanup();
  };
}, [dependency]); // 依赖数组
```

**useCallback - 函数缓存**:
```typescript
const handleSubmit = useCallback((data: FormData) => {
  // 处理提交
}, [dependency]);
```

**useMemo - 计算缓存**:
```typescript
const expensiveValue = useMemo(() => {
  return computeExpensiveValue(input);
}, [input]);
```

**自定义 Hook**:
```typescript
function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authApi.getCurrentUser()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  return { user, loading };
}

// 使用
const { user, loading } = useAuth();
```

---

## 状态管理

React 应用的状态管理有多个层次，从简单的本地状态到复杂的全局状态。

### 本地状态

本地状态是组件私有的，只在组件内部使用。使用 useState Hook 管理本地状态是最简单直接的方式。

对于简单的值（数字、字符串、布尔值），直接使用 useState 即可。对于对象和数组，更新时需要创建新的对象或数组，而不是修改原有的。这是因为 React 使用浅比较来判断状态是否改变。

更新对象状态时，使用扩展运算符 (`...`) 创建新对象，只修改需要改变的属性。这种不可变更新模式是 React 状态管理的核心概念。

```typescript
// 简单状态
const [count, setCount] = useState(0);

// 对象状态
const [form, setForm] = useState({
  username: "",
  password: "",
});

// 更新对象状态
setForm(prev => ({ ...prev, username: newValue }));
```

### Context 状态

当多个组件需要共享状态时，可以使用 Context API。Context 提供了一种在组件树中传递数据的方式，避免了通过 props 逐层传递。

创建 Context 需要三个步骤：首先使用 createContext 创建 Context 对象；然后创建 Provider 组件来提供状态值；最后创建自定义 Hook 来方便地使用 Context。

Context 适合管理全局或跨多个组件的状态，如用户认证信息、主题设置、语言偏好等。但要注意，Context 的任何变化都会导致所有使用它的组件重新渲染，所以不适合频繁变化的状态。

```typescript
// 创建 Context
import { createContext, useContext, useState } from "react";

interface ThemeContextType {
  theme: "light" | "dark";
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | null>(null);

// Provider 组件
export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  const toggleTheme = () => {
    setTheme(prev => prev === "light" ? "dark" : "light");
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

// 使用 Context
export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}

// 在组件中使用
function MyComponent() {
  const { theme, toggleTheme } = useTheme();
  return <button onClick={toggleTheme}>Toggle {theme}</button>;
}
```

---

## API 集成

前端与后端的通信是应用的核心功能之一。本项目封装了一个类型安全的 API 客户端，统一管理所有的 HTTP 请求。

### API 客户端设计

API 客户端采用面向对象的设计，将所有 API 相关的逻辑封装在一个类中。这种设计的好处是：

1. **统一的请求处理** - 所有请求都经过同一个方法，可以统一添加请求头、处理认证、记录日志等
2. **错误处理集中化** - 在一个地方处理所有的 HTTP 错误，避免在每个请求中重复错误处理逻辑
3. **类型安全** - 使用 TypeScript 泛型，每个 API 调用都有明确的返回类型
4. **易于测试** - 可以轻松地模拟 API 客户端进行单元测试

客户端默认发送 JSON 格式的数据，并自动设置 Content-Type 头。`credentials: "include"` 配置确保浏览器在跨域请求时也会发送 cookies，这对于基于 session 的认证很重要。

**lib/api.ts**:
```typescript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      credentials: "include", // 发送 cookies
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: "GET" });
  }

  async post<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async put<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: "DELETE" });
  }
}

export const apiClient = new ApiClient(API_BASE_URL);
```

### 认证 API

认证是应用安全的基础。认证 API 封装了用户登录、登出和获取当前用户信息的功能。

登录成功后，服务器会设置一个 HTTP-only cookie，后续的请求会自动携带这个 cookie 进行身份验证。这种方式比在 localStorage 中存储 token 更安全，因为 JavaScript 无法访问 HTTP-only cookie，可以防止 XSS 攻击。

getCurrentUser 方法用于检查用户是否已登录。应用启动时通常会调用这个方法来恢复用户的登录状态。如果请求失败（例如返回 401 未授权），说明用户未登录或 session 已过期。

```typescript
export const authApi = {
  async login(username: string, password: string): Promise<AuthUser> {
    return apiClient.post("/api/auth/login", { username, password });
  },

  async logout(): Promise<void> {
    return apiClient.post("/api/auth/logout", {});
  },

  async getCurrentUser(): Promise<AuthUser> {
    return apiClient.get("/api/auth/me");
  },
};
```

### 查询 API

查询 API 是应用的核心功能，支持两种模式：普通查询和流式查询。

**普通查询** 会等待服务器完全生成答案后一次性返回。这种方式实现简单，但用户需要等待较长时间才能看到结果。适用于对响应时间要求不高的场景。

**流式查询** 使用 Server-Sent Events (SSE) 技术，服务器生成答案的过程中会逐步推送内容。用户可以立即看到答案开始生成，体验类似于 ChatGPT。这种方式的实现稍复杂，需要处理流式数据和解析 SSE 格式。

流式查询使用了 async generator 函数（`async function*`），它可以逐步 yield 数据块。调用方使用 `for await...of` 循环来接收数据。这种模式很适合处理流式数据。

```typescript
export const queryApi = {
  async query(sessionId: string, question: string): Promise<QueryResponse> {
    return apiClient.post("/api/query", {
      session_id: sessionId,
      question,
    });
  },

  async *queryStream(
    sessionId: string,
    question: string
  ): AsyncGenerator<string> {
    const response = await fetch(`${API_BASE_URL}/api/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, question }),
      credentials: "include",
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader!.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split("\n");

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") return;
          yield JSON.parse(data).content;
        }
      }
    }
  },
};
```

---

## 路由管理

路由管理负责根据 URL 显示不同的页面，是单页应用（SPA）的核心功能。

### 路由配置

React Router 使用声明式的方式配置路由。每个 `<Route>` 元素定义了一个路径和对应的组件。`<Routes>` 组件会根据当前 URL 匹配并渲染对应的路由。

**嵌套路由** 允许在父路由中渲染子路由，适用于有固定布局的多页面应用。

**懒加载** 通过 `React.lazy` 和 `import()` 实现，可以将不同路由的代码分割成不同的文件，只在需要时才加载。这可以显著减少初始加载时间，特别是对于大型应用。

**重定向** 使用 `<Navigate>` 组件，可以将用户从一个路径重定向到另一个路径。例如将根路径重定向到默认页面。

**404 处理** 通过 `path="*"` 匹配所有未定义的路径，显示 404 页面。

```typescript
import { Routes, Route, Navigate } from "react-router-dom";

export function App() {
  return (
    <Routes>
      {/* 公开路由 */}
      <Route path="/app/login" element={<LoginPage />} />
      
      {/* 受保护路由 */}
      <Route
        path="/app"
        element={
          <Protected>
            <ChatPage />
          </Protected>
        }
      />
      
      <Route
        path="/app/admin"
        element={
          <AdminRoute>
            <AdminPage />
          </AdminRoute>
        }
      />
      
      {/* 重定向 */}
      <Route path="/" element={<Navigate to="/app" replace />} />
      
      {/* 404 */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
```

### 路由守卫

路由守卫用于保护需要认证或特定权限的路由。它是一个高阶组件，在渲染实际内容前检查用户的认证状态和权限。

**Protected 组件** 检查用户是否已登录。如果正在加载用户信息，显示加载指示器；如果未登录，重定向到登录页；否则渲染子组件。

**AdminRoute 组件** 在 Protected 的基础上增加了角色检查。只有角色为 "admin" 的用户才能访问，其他用户会被重定向到普通用户页面。

这种模式可以扩展到更复杂的权限系统，例如基于多个角色或细粒度的权限。

```typescript
function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) return <div>Loading...</div>;
  if (!user) return <Navigate to="/app/login" replace />;

  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) return <div>Loading...</div>;
  if (!user) return <Navigate to="/app/login" replace />;
  if (user.role !== "admin") return <Navigate to="/app" replace />;

  return <>{children}</>;
}
```

### 编程式导航

除了通过 `<Link>` 组件进行导航，有时需要在代码中执行导航，例如表单提交成功后跳转到其他页面。

`useNavigate` Hook 返回一个导航函数，可以接受路径字符串或数字。传入字符串会导航到指定路径；传入负数会在历史记录中后退相应步数，传入正数会前进。

`replace` 选项会替换当前的历史记录条目而不是添加新条目，这在重定向场景中很有用。

```typescript
import { useNavigate } from "react-router-dom";

function MyComponent() {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate("/app/admin");
  };

  const handleBack = () => {
    navigate(-1); // 返回上一页
  };

  return (
    <>
      <button onClick={handleClick}>Go to Admin</button>
      <button onClick={handleBack}>Go Back</button>
    </>
  );
}
```

---

## 样式系统

前端样式采用 CSS Modules 配合 CSS 变量的方案，既保持了样式的模块化，又支持全局主题切换。

### CSS Modules

CSS Modules 是一种将 CSS 作用域限定在组件级别的技术。每个 CSS 类名在构建时都会被转换为唯一的标识符，从而避免全局命名冲突。

使用 CSS Modules 的好处包括：
1. **样式隔离** - 不用担心类名冲突，可以在不同组件中使用相同的类名
2. **依赖明确** - 样式文件需要显式导入，容易追踪哪些组件使用了哪些样式
3. **易于删除** - 删除组件时可以安全地删除对应的样式文件
4. **保持 CSS 原生** - 不需要学习新的语法，仍然是标准的 CSS

CSS 变量（自定义属性）用于定义主题相关的颜色、间距等值。通过修改根元素的变量值，可以轻松实现主题切换。

```css
/* MyComponent.module.css */
.container {
  padding: 1rem;
  background: var(--bg-primary);
}

.title {
  font-size: 1.5rem;
  color: var(--text-primary);
}

.button {
  padding: 0.5rem 1rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.button:hover {
  background: var(--color-primary-dark);
}
```

```typescript
// MyComponent.tsx
import styles from "./MyComponent.module.css";

export function MyComponent() {
  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Title</h2>
      <button className={styles.button}>Click</button>
    </div>
  );
}
```

### 条件类名

实际开发中经常需要根据状态或 props 动态应用不同的类名。虽然可以使用模板字符串拼接，但 clsx 库提供了更优雅的 API。

clsx 接受多种参数类型：字符串、对象、数组等，并智能地组合它们。对于对象参数，键是类名，值是布尔表达式，只有值为真时该类名才会被包含。

这种方式使代码更加清晰，特别是在有多个条件类名时。相比手动拼接字符串，clsx 还会自动过滤掉假值，避免出现多余的空格。

```typescript
import clsx from "clsx";

function Button({ variant, size, disabled }: ButtonProps) {
  return (
    <button
      className={clsx(
        styles.button,
        styles[variant], // styles.primary or styles.secondary
        styles[size],    // styles.small or styles.large
        disabled && styles.disabled
      )}
    >
      Click me
    </button>
  );
}
```

### 主题系统

主题系统允许用户在亮色和暗色模式之间切换，提升不同环境下的使用体验。

主题切换的实现基于 CSS 变量和 HTML 属性选择器。根元素的 `data-theme` 属性决定当前主题，不同主题使用不同的 CSS 变量值。

"auto" 模式会根据系统偏好自动选择主题。`window.matchMedia` 可以查询系统的颜色方案偏好，在支持暗色模式的操作系统上，用户的系统设置会影响这个查询结果。

主题偏好保存在 localStorage 中，这样用户下次访问时能保持之前选择的主题。

```typescript
// lib/theme.ts
export type ThemeMode = "light" | "dark" | "auto";

export function applyTheme(theme: ThemeMode) {
  const root = document.documentElement;
  
  if (theme === "auto") {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    theme = prefersDark ? "dark" : "light";
  }
  
  root.setAttribute("data-theme", theme);
}

export function saveTheme(theme: ThemeMode) {
  localStorage.setItem("theme", theme);
}

export function getSavedTheme(): ThemeMode {
  return (localStorage.getItem("theme") as ThemeMode) || "auto";
}
```

```css
/* 全局样式 */
:root {
  --color-primary: #3b82f6;
  --bg-primary: #ffffff;
  --text-primary: #1f2937;
}

[data-theme="dark"] {
  --color-primary: #60a5fa;
  --bg-primary: #1f2937;
  --text-primary: #f3f4f6;
}
```

---

## 国际化

国际化（i18n）使应用能够支持多种语言，满足不同地区用户的需求。

### 国际化架构

本项目使用 i18next 作为国际化框架，它是 JavaScript 生态中最成熟的 i18n 解决方案之一。react-i18next 提供了 React 特定的绑定，包括 Hook 和 HOC。

翻译文件组织为 JSON 格式，每种语言一个文件。使用嵌套的对象结构可以更好地组织翻译内容，避免键名冲突。例如 `common.login` 表示通用模块的登录文本。

i18next 支持插值（在翻译文本中插入动态值）、复数处理、上下文等高级特性。配置中的 `fallbackLng` 指定找不到翻译时使用的备用语言。

### 配置

**i18n/config.ts**:
```typescript
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import zh from "./locales/zh.json";

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    zh: { translation: zh },
  },
  lng: "zh", // 默认语言
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
```

### 翻译文件

翻译文件使用 JSON 格式，采用命名空间组织。`common` 命名空间存放通用的翻译，如按钮文本、常见操作等；`chat` 命名空间存放聊天相关的翻译。

这种组织方式使翻译文件结构清晰，也便于按需加载。对于大型应用，可以将不同功能模块的翻译分开，只在需要时加载。

保持中英文翻译的结构一致很重要，这样可以避免运行时因为找不到翻译键而出错。

**locales/en.json**:
```json
{
  "common": {
    "login": "Login",
    "logout": "Logout",
    "submit": "Submit",
    "cancel": "Cancel"
  },
  "chat": {
    "inputPlaceholder": "Type your question...",
    "send": "Send"
  }
}
```

**locales/zh.json**:
```json
{
  "common": {
    "login": "登录",
    "logout": "登出",
    "submit": "提交",
    "cancel": "取消"
  },
  "chat": {
    "inputPlaceholder": "输入您的问题...",
    "send": "发送"
  }
}
```

### 使用翻译

在组件中使用翻译很简单，通过 `useTranslation` Hook 获取翻译函数 `t` 和 i18n 实例。

`t` 函数接受翻译键（如 "common.login"）并返回对应语言的文本。它还支持插值，可以在翻译文本中使用变量。

`i18n.changeLanguage` 方法用于切换语言。切换语言后，所有使用了 `useTranslation` 的组件会自动重新渲染并显示新语言的文本。

语言偏好也应该保存到 localStorage，这样用户下次访问时能保持之前的语言选择。

```typescript
import { useTranslation } from "react-i18next";

function MyComponent() {
  const { t, i18n } = useTranslation();

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };

  return (
    <div>
      <h1>{t("common.login")}</h1>
      <button onClick={() => changeLanguage("en")}>English</button>
      <button onClick={() => changeLanguage("zh")}>中文</button>
    </div>
  );
}
```

---

## 测试

前端测试确保组件按预期工作，及早发现 bug，也为重构提供安全网。

### 测试策略

测试应该覆盖组件的关键行为：
1. **渲染测试** - 验证组件能正确渲染，显示预期的内容
2. **交互测试** - 验证用户交互（点击、输入等）产生预期的结果
3. **状态测试** - 验证组件状态变化时 UI 正确更新
4. **边界测试** - 验证边界情况和错误处理

测试应该从用户角度编写，关注组件的行为而不是实现细节。这样即使重构了组件内部实现，只要行为不变，测试就不需要修改。

### 组件测试

React Testing Library 提倡编写贴近用户使用方式的测试。例如通过文本内容或 ARIA 角色查找元素，而不是通过 CSS 类名或测试 ID。

`render` 函数渲染组件到虚拟 DOM。`screen` 提供了查询元素的方法，如 `getByText`、`getByRole` 等。`fireEvent` 用于触发事件，如点击、输入等。

测试应该是独立的，每个测试运行在独立的环境中，不受其他测试影响。使用 `describe` 和 `it` 组织测试，`describe` 对相关测试分组，`it` 描述单个测试用例。

```typescript
// MyComponent.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { MyComponent } from "./MyComponent";

describe("MyComponent", () => {
  it("renders correctly", () => {
    render(<MyComponent title="Test" />);
    expect(screen.getByText("Test")).toBeInTheDocument();
  });

  it("handles click", () => {
    const handleClick = jest.fn();
    render(<MyComponent title="Test" onUpdate={handleClick} />);
    
    const button = screen.getByRole("button");
    fireEvent.click(button);
    
    expect(handleClick).toHaveBeenCalledWith(1);
  });
});
```

---

## 最佳实践

遵循最佳实践可以提高代码质量，使项目更易于维护和扩展。

### 1. 组件设计

**保持组件小而专注** - 每个组件应该只负责一个功能。如果组件变得复杂，考虑拆分成更小的子组件。小组件更容易理解、测试和复用。

**使用 TypeScript 类型** - 为所有组件定义 Props 接口，为函数定义参数和返回值类型。类型系统能在编译时发现很多错误，也提供了更好的 IDE 支持。

**Props 使用接口定义** - 使用 `interface` 而不是 `type` 定义 Props，因为 interface 更适合描述对象形状，也能更好地与 React 开发工具集成。

### 2. 性能优化

**使用 React.memo 避免不必要的重渲染** - 对于纯展示组件，使用 `React.memo` 可以在 props 未变化时跳过重新渲染。但不要过度使用，只在性能分析发现问题时才优化。

**使用 useCallback 和 useMemo** - 对于传递给子组件的回调函数使用 `useCallback`，对于开销大的计算使用 `useMemo`。但要注意这些 Hook 本身也有开销，不是所有情况都需要。

**懒加载路由组件** - 使用 `React.lazy` 和动态 `import()` 按需加载路由组件，减少初始加载的代码量。配合 `<Suspense>` 显示加载状态。

### 3. 代码组织

**一个文件一个组件** - 每个组件文件应该只导出一个主要组件。这使得文件职责清晰，也便于代码分割。

**相关文件放在一起** - 组件的样式、测试等文件应该和组件文件放在同一目录。这种组织方式称为"按功能组织"，优于"按类型组织"。

**使用索引文件导出** - 在目录中创建 `index.ts` 文件，统一导出该目录的公共 API。这样其他模块导入时可以只指定目录名。

### 4. 样式管理

**使用 CSS Modules** - 保持样式的模块化，避免全局样式污染。

**定义 CSS 变量** - 将颜色、间距等常用值定义为 CSS 变量，便于统一管理和主题切换。

**避免内联样式** - 内联样式难以维护，也无法使用 CSS 的高级特性如伪类、媒体查询等。只在需要动态计算样式值时才使用。

---

## 下一步

了解前端开发后，建议继续阅读：

1. **[API 开发](./API_DEVELOPMENT.md)** - 了解后端 API 的实现
2. **[系统架构](./ARCHITECTURE.md)** - 理解前后端如何协同工作
3. **[配置参考](./CONFIGURATION_REFERENCE.md)** - 了解环境变量配置

如果你是全栈开发者，建议按以下顺序学习：
1. 先学习后端开发（API 开发、多智能体系统、数据存储）
2. 再学习前端开发（本文档）
3. 最后将前后端集成，构建完整的应用

---

**更新日期**: 2026-06-19  
**文档版本**: 1.1
