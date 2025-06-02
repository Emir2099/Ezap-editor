# EZap Editor

A modern, beginner-friendly Python code editor built with PyQt5, featuring a vibrant UI, async operations, and advanced usability enhancements.

## ✨ Features
- **Modern, glassy/neon UI** with gradients, rounded corners, and vibrant colors
- **File Explorer** panel for easy file browsing and opening
- **Command Palette** (Ctrl+Shift+P) with sci-fi animation and mouse/keyboard navigation
- **Quick File Switcher** (Ctrl+P) for fast file switching
- **Animated notifications** (e.g., "File saved!")
- **Async package management** (no UI freeze)
- **Animated panel transitions** (e.g., File Explorer toggle with Ctrl+B)
- **Keyboard and touchpad gesture support**
- **Beginner-friendly welcome screen and tooltips**
- **Light/Dark mode and font size settings**
- **Inline error tooltips and clickable error lines**

## 🚀 Installation
1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd Ezap\ editor
   ```
2. **Install dependencies:**
   ```bash
   pip install PyQt5 qtawesome
   ```
3. **Run the editor:**
   ```bash
   python main.py
   ```

## 🖥️ Usage
- **Open files:** Use the File Explorer or `Ctrl+O`
- **Save files:** `Ctrl+S`
- **Run code:** `F5`
- **Command palette:** `Ctrl+Shift+P`
- **Quick file switcher:** `Ctrl+P`
- **Toggle File Explorer:** `Ctrl+B`
- **Settings:** Change theme and font size from the menu or palette
- **Package management:** Install/uninstall Python packages from the menu or palette

## ⚡ Modern UI Highlights
- Animated transitions and notifications
- Neon/glassy look inspired by futuristic editors
- Async operations for a smooth, responsive experience
- Touchpad and keyboard navigation throughout

## ⚠️ Limitations
- Some advanced UI/UX features (blur, true CSS effects, ultra-smooth animations) are limited by PyQt5's stylesheet system
- For a truly "VS Code-level" experience, consider migrating to Electron, Tauri, or Flutter (see below)

## 🛣️ Future Plans
- **Migration to Electron/Tauri/Flutter** for even more advanced UI, plugin ecosystem, and performance
- **AI code suggestions, live linting, and more**

---

**EZap Editor** is a showcase of what's possible with PyQt5, but also a stepping stone to even more powerful, modern code editors. Contributions and suggestions are welcome! 