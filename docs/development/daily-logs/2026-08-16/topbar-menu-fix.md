# Topbar Menu Button Fix

## Issue
The three-dot menu button (⋮) in the top-right corner was not visible.

## Root Cause
The CSS selector `.page-shell .topbar.topbar-minimal` in `hidden-sections.css` was incorrect because:
- The `ChatTopbar` component is rendered **outside** the `page-shell` div (as a sibling)
- The selector required the topbar to be a **descendant** of `.page-shell`
- This caused the CSS rules to not apply to the topbar

## Fix Applied
Changed the CSS selector in `frontend/src/styles/features/hidden-sections.css`:

**Before:**
```css
.page-shell .topbar.topbar-minimal {
  /* styles */
}
```

**After:**
```css
.topbar.topbar-minimal {
  /* styles */
}
```

## Additional Improvements
1. Added `z-index: 10001` to `.topbar-menu-container` for better stacking
2. Added `position: relative` and `z-index: 10002` to `.topbar-menu-trigger` to ensure button is always on top
3. Kept `.page-shell .topbar` selector for regular topbar styles (inside page-shell)

## Result
The three-dot menu button should now be visible in the top-right corner at position (16px, 16px) from the edge, with:
- Dark semi-transparent background: `rgba(30, 41, 59, 0.95)`
- Light text color: `#e2e8f0`
- Proper hover effects and transitions
- High z-index (10002) to stay above other content

## Testing
1. Open the app at http://127.0.0.1:5177/
2. Look at the top-right corner
3. The ⋮ button should be visible
4. Click it to see the dropdown menu
5. Test all menu options (language, theme, settings, etc.)
