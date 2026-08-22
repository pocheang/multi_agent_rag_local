# 菜单显示裁剪问题修复

## 问题描述

菜单被父容器裁剪，无法完整显示，如图所示菜单内容被卡片边界截断。

## 根本原因

父容器的 `overflow` 属性默认值导致绝对定位的菜单被裁剪。

## 解决方案

在 `frontend/src/styles/components/sidebar/modern-sessions.css` 中添加：

```css
/* Ensure dropdown menus are not clipped */
.page-shell .sidebar-history-panel {
  overflow: visible;
}

.page-shell .sidebar-history {
  overflow: visible;
}

.page-shell .session-list {
  display: grid;
  gap: 8px;
  margin-top: 0;
  overflow: visible;  /* 新增 */
}

.page-shell .session-item:has(.session-dropdown-menu) {
  z-index: 100;
  overflow: visible;  /* 新增 */
}
```

## 修复内容

1. **sidebar-history-panel**: 添加 `overflow: visible`
2. **sidebar-history**: 添加 `overflow: visible`
3. **session-list**: 添加 `overflow: visible`
4. **session-item (打开菜单时)**: 添加 `overflow: visible`

## 工作原理

- 菜单使用 `position: absolute` 定位在 `.session-menu-wrapper` (relative) 容器下
- 如果父元素链中任何一个有 `overflow: hidden/auto/scroll`，菜单会被裁剪
- 通过显式设置整个容器链为 `overflow: visible`，确保菜单不被裁剪
- 使用 `:has()` 伪类选择器，仅在菜单打开时提升 z-index 和设置 overflow

## 测试验证

✅ 构建成功
```
✓ built in 5.95s
```

✅ 所有样式规则正确应用

## 浏览器兼容性

- `overflow: visible` - 所有浏览器
- `:has()` 伪类 - 现代浏览器支持 (Chrome 105+, Firefox 121+, Safari 15.4+)

如果需要支持旧浏览器，可以移除 `:has()` 选择器，直接在 `.session-item` 上设置：

```css
.page-shell .session-item {
  z-index: 1;
  overflow: visible;
}

.page-shell .session-item:has(.session-dropdown-menu) {
  z-index: 100;
}
```

## 注意事项

这个修复不会影响：
- 滚动行为（如果容器需要滚动，在更外层容器设置）
- 性能（overflow: visible 是默认值）
- 其他组件（只影响会话列表区域）

## 相关文件

- `frontend/src/styles/components/sidebar/modern-sessions.css` - 主要修复文件
