import { Link } from "react-router-dom";

export function NotFoundPage({ pathname }: { pathname: string }) {
  return (
    <div className="not-found">
      <h1>404</h1>
      <p>未找到页面: {pathname}</p>
      <div className="top-actions">
        <Link className="secondary link-btn" to="/app">
          返回应用
        </Link>
        <Link className="secondary link-btn" to="/app/login">
          去登录
        </Link>
      </div>
    </div>
  );
}
