# 双语支持功能 - 使用指南

## 快速开始

### 用户使用
1. 点击页面上的 🌐 按钮切换语言（English / 中文）
2. 语言偏好自动保存，刷新页面后保持

### 开发者集成

在组件中使用翻译：
```tsx
import { useTranslation } from 'react-i18next';

function MyComponent() {
  const { t } = useTranslation();
  return <h1>{t('mySection.title')}</h1>;
}
```

## 文件结构

```
src/
├── i18n/
│   ├── config.ts              # i18n 配置
│   └── locales/
│       ├── en.json            # 英文翻译（161 keys）
│       └── zh.json            # 中文翻译（161 keys）
├── components/
│   └── LanguageToggle.tsx     # 语言切换按钮
└── styles/components/
    └── language-toggle.css    # 按钮样式
```

## 已翻译的内容

- ✅ LoginPage - 登录/注册页面
- ✅ ArchitecturePage - 架构文档页面（8个章节 + 58个列表项 + API文档）
- ✅ DataFlowVisualization - 数据流图表（28个节点）
- ✅ 语言切换按钮
- ✅ 主题切换按钮
- ✅ 功能卡片

## 添加新翻译

1. 在 `en.json` 和 `zh.json` 中添加对应的键值对
2. 在组件中使用 `t('your.key')`
3. 确保两个文件的键完全对应

## 技术实现

- 使用 i18next (^26.3.1) 和 react-i18next (^17.0.8)
- localStorage 持久化语言偏好
- 支持动态切换，无需刷新页面
- 所有翻译键完全类型安全

---

**完成时间**: 2026-06-03  
**状态**: ✅ 生产就绪
