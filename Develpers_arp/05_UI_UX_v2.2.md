# UI & UX Standards - SIMS v2.2

1. **Speed > Animation:** Do not use full-page route animations for internal module changes. Swap content dynamically inside `ContentHost.mount()`.
2. **Premium Feel:** Use elegant spacing (`padding=30`), subtle box shadows on cards, and glassy/acrylic hover effects on the sidebar.
3. **Empty States:** Never show a blank table. Always display a placeholder icon and text (e.g., "No students found. Add one to begin.").
4. **Error Handling:** Never expose raw Python tracebacks. Use red `ft.Text` for inline validation or elegant Toast notifications for system errors.
