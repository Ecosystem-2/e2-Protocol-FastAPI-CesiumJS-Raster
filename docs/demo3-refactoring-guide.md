# Demo3 Workflow Refactoring Guide

## Problem Statement
HTML files in `demo3-workflow/` were becoming unwieldy (400-500+ lines each) with:
- Inline `<style>` blocks (200+ lines of CSS)
- Inline `<script>` blocks (300+ lines of JavaScript)
- Repeated patterns across steps
- Poor separation of concerns

## New Architecture

### File Structure
```
app/demo/
├── static/
│   ├── demo3-common.js       # Shared utilities (existing)
│   ├── demo3-styles.css      # Shared styles (existing)
│   ├── step1_upload.css      # Step 1 specific styles
│   ├── step1_upload.js       # Step 1 logic
│   ├── step5_export.css      # Step 5 specific styles
│   └── step5_export.js       # Step 5 logic
└── demo3-workflow/
    ├── step1_upload.html     # Minimal structure (150 lines)
    └── step5_export.html     # Minimal structure (120 lines)
```

### Separation of Concerns

**1. HTML (Structure Only)**
- Semantic markup
- No inline styles or scripts
- External CSS/JS links
- ~60-80% reduction in file size

**2. CSS Files**
- `demo3-styles.css` - Shared styles (buttons, panels, navigation)
- `stepN_*.css` - Page-specific styles (file inputs, cards, etc.)

**3. JavaScript Files**
- `demo3-common.js` - Shared utilities (API, UI, WorkflowState)
- `stepN_*.js` - Page-specific logic (event handlers, business logic)

### Benefits

✅ **Maintainability**
- Single responsibility per file
- Easy to locate code (HTML = structure, CSS = styling, JS = behaviour)
- No scrolling through 500-line files

✅ **Reusability**
- Common styles/utilities centralised
- Page-specific code isolated
- Easy to apply patterns to new steps

✅ **Performance**
- Browser caches external CSS/JS
- Faster page loads after first visit
- Parallel resource loading

✅ **Collaboration**
- Designers can work on CSS without touching JS
- Developers can work on JS without touching HTML
- Reduced merge conflicts

✅ **Testing**
- JavaScript modules can be unit tested
- CSS can be validated independently
- HTML structure can be linted

### Migration Pattern

**Before (Monolithic)**:
```html
<!-- step1_upload.html - 500+ lines -->
<head>
  <style>
    /* 200 lines of CSS */
  </style>
</head>
<body>
  <!-- 150 lines of HTML -->
  <script>
    // 300 lines of JavaScript
  </script>
</body>
```

**After (Modular)**:
```html
<!-- step1_upload.html - 150 lines -->
<head>
  <link rel="stylesheet" href="../static/demo3-styles.css">
  <link rel="stylesheet" href="../static/step1_upload.css">
</head>
<body>
  <!-- 150 lines of clean HTML -->
  <script src="../static/demo3-common.js"></script>
  <script src="../static/step1_upload.js"></script>
</body>
```

### Apply to Other Steps

**Step 2 (Tiles)**:
```bash
# Extract styles
app/demo/static/step2_tiles.css

# Extract logic
app/demo/static/step2_tiles.js

# Update HTML
- Remove <style> block
- Remove <script> block
+ <link rel="stylesheet" href="../static/step2_tiles.css">
+ <script src="../static/step2_tiles.js"></script>
```

**Step 3 (Draw)**:
```bash
app/demo/static/step3_draw.css
app/demo/static/step3_draw.js
```

**Step 4 (Save)**:
```bash
app/demo/static/step4_save.css
app/demo/static/step4_save.js
```

### Common Patterns to Extract

**1. API Code Examples Component**
```html
<!-- Repeated across multiple steps -->
<details class="api-example">
  <summary>📋 API Request Example</summary>
  <!-- ... -->
</details>
```
**Move to**: `demo3-styles.css` for `.api-example` styles

**2. Control Panels**
```css
/* Shared panel styling */
.control-panel { /* ... */ }
.control-group { /* ... */ }
```
**Already in**: `demo3-styles.css`

**3. Status Messages**
```javascript
// Shared UI utilities
UI.showStatus(message, isError)
UI.showSuccess(message)
UI.showResults(title, data)
```
**Already in**: `demo3-common.js`

### Refactoring Checklist

For each step HTML file:

- [ ] Create `stepN_*.css` file
  - Extract all `<style>` content
  - Remove page-specific overrides already in `demo3-styles.css`
  - Keep only unique styles for this step

- [ ] Create `stepN_*.js` file
  - Extract all `<script>` content
  - Remove functions already in `demo3-common.js`
  - Keep only page-specific logic

- [ ] Update HTML file
  - Remove `<style>` block
  - Remove `<script>` block
  - Add CSS `<link>` tags
  - Add JS `<script>` tags at end of `<body>`

- [ ] Test functionality
  - Verify all styles render correctly
  - Verify all JavaScript works
  - Check browser console for errors
  - Test navigation between steps

### Browser Caching Strategy

```html
<!-- For production, add version query strings -->
<link rel="stylesheet" href="../static/step1_upload.css?v=1.0.0">
<script src="../static/step1_upload.js?v=1.0.0"></script>

<!-- Or use build tools to generate hashed filenames -->
<link rel="stylesheet" href="../static/step1_upload.abc123.css">
<script src="../static/step1_upload.def456.js"></script>
```

### Future Enhancements

**Component Library** (if needed):
```
app/demo/components/
├── ApiExample.js        # Reusable API code example component
├── SelectionCard.js     # Site/selection card component
├── StatsGrid.js         # Statistics display component
└── FileUploader.js      # File upload widget
```

**Build Process** (if needed):
```bash
# Minify CSS/JS for production
npm run build:demo

# Output
app/demo/dist/
├── step1_upload.min.css
└── step1_upload.min.js
```

**TypeScript** (if needed):
```typescript
// step1_upload.ts with type safety
interface UploadData {
  asset_id: string;
  asset: AssetRecord;
  raster: RasterSummary;
  replaced: boolean;
}
```

## Summary

This refactoring reduces HTML file sizes by ~70% while improving:
- Code organisation
- Maintainability
- Performance (caching)
- Developer experience
- Team collaboration

Apply the same pattern to remaining steps (2, 3, 4) for consistency.
