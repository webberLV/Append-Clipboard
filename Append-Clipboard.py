import tkinter as tk
from tkinter import messagebox
import os
import sys
import ctypes

# Try to import drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    print("Warning: tkinterdnd2 not available. Install with: pip install tkinterdnd2")


def is_probably_text(path, sample_size=8192):
    try:
        with open(path, 'rb') as f:
            b = f.read(sample_size)
        if not b:
            return True
        if b.count(b'\x00') > 0:
            return False
        bad = 0
        for c in b:
            if c < 9 or (13 < c < 32) or c == 127:
                bad += 1
        return (bad / len(b)) < 0.20
    except:
        return False


class AlwaysOnTopClipboard:
    def __init__(self):
        # Create window with drag-and-drop support if available
        if DND_AVAILABLE:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()

        self.WIDTH = 500
        self.HEIGHT = 60

        self.setup_window()
        self.create_widgets()
        self.make_always_on_top()

    def setup_window(self):
        """Configure the main window"""
        self.root.title("File Clipboard Tool")
        self.root.configure(bg='black')

        # Remove window decorations (borderless)
        self.root.overrideredirect(True)

        # Make window transparent - black becomes invisible
        self.root.attributes('-transparentcolor', 'black')

        # Always on top - must be set AFTER window creation
        self.root.attributes('-topmost', True)

        # Center to top-middle of primary screen on first launch
        screen_w = self.root.winfo_screenwidth()
        x = max(0, (screen_w - self.WIDTH) // 2)
        y = 0
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        # Variables for dragging
        self.drag_x = 0
        self.drag_y = 0

    def make_always_on_top(self):
        """Make window always on top using Windows API"""
        if sys.platform == 'win32':
            try:
                # Get window handle
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())

                # HWND_TOPMOST = -1
                # SWP_NOMOVE | SWP_NOSIZE = 0x0003
                ctypes.windll.user32.SetWindowPos(
                    hwnd, -1, 0, 0, 0, 0, 0x0003
                )
            except Exception as e:
                print(f"Could not set always-on-top: {e}")
        else:
            # For non-Windows platforms
            self.root.attributes('-topmost', True)

    def create_widgets(self):
        """Create the UI elements"""
        # Container for buttons
        container = tk.Frame(self.root, bg='black')
        container.pack(fill='both', expand=True)

        # APPEND Button (left) - 50% smaller
        self.append_btn = tk.Label(
            container,
            text="📎 APPEND",
            bg='#2d4a87', fg='#ffffff',
            font=('Segoe UI', 9, 'bold'),
            relief='raised', bd=2,
            padx=15, pady=15,
            cursor='hand2'
        )
        self.append_btn.place(x=0, y=0)

        # CLOSE Button (center, between the two buttons)
        self.close_btn = tk.Label(
            container,
            text="X",
            bg='#8b2a2a', fg='#ffffff',
            font=('Segoe UI', 12, 'bold'),
            relief='raised', bd=2,
            padx=12, pady=12,
            cursor='hand2'
        )
        self.close_btn.place(x=200, y=0)
        self.close_btn.bind('<Button-1>', lambda e: self.root.quit())

        # REPLACE Button (right, 400px away) - 50% smaller
        self.replace_btn = tk.Label(
            container,
            text="🔄 REPLACE",
            bg='#4a7c59', fg='#ffffff',
            font=('Segoe UI', 9, 'bold'),
            relief='raised', bd=2,
            padx=15, pady=15,
            cursor='hand2'
        )
        self.replace_btn.place(x=400, y=0)

        # Make buttons draggable for repositioning the whole window
        self.append_btn.bind('<Button-1>', self.start_drag)
        self.append_btn.bind('<B1-Motion>', self.do_drag)
        self.replace_btn.bind('<Button-1>', self.start_drag)
        self.replace_btn.bind('<B1-Motion>', self.do_drag)

        # Setup drag and drop
        if DND_AVAILABLE:
            self.append_btn.drop_target_register(DND_FILES)
            self.append_btn.dnd_bind('<<Drop>>', lambda e: self.on_drop(e, append=True))

            self.replace_btn.drop_target_register(DND_FILES)
            self.replace_btn.dnd_bind('<<Drop>>', lambda e: self.on_drop(e, append=False))

            # Visual feedback on drag over
            self.append_btn.dnd_bind('<<DropEnter>>', lambda e: self.append_btn.configure(bg='#3d5a97'))
            self.append_btn.dnd_bind('<<DropLeave>>', lambda e: self.append_btn.configure(bg='#2d4a87'))

            self.replace_btn.dnd_bind('<<DropEnter>>', lambda e: self.replace_btn.configure(bg='#5a8c69'))
            self.replace_btn.dnd_bind('<<DropLeave>>', lambda e: self.replace_btn.configure(bg='#4a7c59'))
        else:
            # Show error if drag-and-drop not available
            self.append_btn.configure(text="❌ APPEND")
            self.replace_btn.configure(text="❌ REPLACE")

    def start_drag(self, event):
        """Start dragging the window"""
        self.drag_x = event.x
        self.drag_y = event.y

    def do_drag(self, event):
        """Handle window dragging"""
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")

    def on_drop(self, event, append=False):
        """Handle file/folder drop"""
        try:
            # Parse dropped items
            items = self.parse_drop_files(event.data)

            if not items:
                self.flash_button(self.append_btn if append else self.replace_btn, '#8b2a2a')
                return

            # Collect all file paths (text-like only)
            all_files = []
            for item in items:
                if os.path.isfile(item):
                    if is_probably_text(item):
                        all_files.append(item)
                elif os.path.isdir(item):
                    folder_files = self.get_all_files_in_folder(item)
                    all_files.extend(folder_files)

            if not all_files:
                self.flash_button(self.append_btn if append else self.replace_btn, '#8b2a2a')
                return

            # Sort files alphabetically
            all_files.sort()

            # Read file contents
            combined_content = []
            successful = 0
            failed = 0

            for file_num, file_path in enumerate(all_files, start=1):
                try:
                    with open(file_path, 'rb') as f:
                        raw_content = f.read()

                    # Try UTF-8, fallback to latin-1
                    try:
                        file_content = raw_content.decode('utf-8')
                    except:
                        file_content = raw_content.decode('latin-1')

                    combined_content.append(f"// File {file_num}/{len(all_files)} - {file_path} //")
                    combined_content.append("")
                    combined_content.append(file_content)
                    combined_content.append("")
                    successful += 1

                except Exception as e:
                    combined_content.append(f"// File {file_num}/{len(all_files)} - {file_path} (ERROR) //")
                    combined_content.append("")
                    combined_content.append(f"Failed to read: {str(e)}")
                    combined_content.append("")
                    failed += 1

            # Create final content
            new_content = '\n'.join(combined_content)

            # Append or replace clipboard
            if append:
                try:
                    existing = self.root.clipboard_get()
                    final_content = existing + '\n\n' + new_content
                except:
                    final_content = new_content
            else:
                final_content = new_content

            # Update clipboard
            self.root.clipboard_clear()
            self.root.clipboard_append(final_content)

            # Visual feedback
            self.flash_button(self.append_btn if append else self.replace_btn, '#4ade80')

            # Show message
            mode = "Appended" if append else "Replaced"
            msg = f"{mode}: {successful} files"
            if failed > 0:
                msg += f" ({failed} failed)"

            self.show_toast(msg)

        except Exception as e:
            print(f"Error: {e}")
            self.flash_button(self.append_btn if append else self.replace_btn, '#8b2a2a')

    def parse_drop_files(self, data):
        """Parse dropped file data"""
        import re
        import shlex

        items = []

        if data.startswith('{'):
            items = re.findall(r'\{([^}]+)\}', data)
        else:
            if '"' in data or "'" in data:
                try:
                    items = shlex.split(data)
                except:
                    items = data.split()
            else:
                items = data.split()

        valid_items = []
        for item in items:
            item = item.strip()
            if item and os.path.exists(item):
                valid_items.append(item)

        return valid_items

    def get_all_files_in_folder(self, folder_path):
        """Recursively get all files in a folder (text-like only)"""
        file_paths = []
        try:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith('.bak'):
                        continue
                    full_path = os.path.join(root, file)
                    if is_probably_text(full_path):
                        file_paths.append(full_path)
        except Exception as e:
            print(f"Error reading folder {folder_path}: {e}")
        return file_paths

    def flash_button(self, button, color):
        """Flash button with a color"""
        original_bg = button.cget('bg')
        button.configure(bg=color)
        self.root.after(200, lambda: button.configure(bg=original_bg))

    def show_toast(self, message):
        """Show a temporary toast message"""
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes('-topmost', True)
        toast.configure(bg='#2a2a2a')

        label = tk.Label(
            toast, text=message,
            bg='#2a2a2a', fg='#ffffff',
            font=('Segoe UI', 9),
            padx=15, pady=8
        )
        label.pack()

        # Position near main window
        x = self.root.winfo_x() + self.root.winfo_width() + 10
        y = self.root.winfo_y()
        toast.geometry(f"+{x}+{y}")

        # Auto-destroy after 2 seconds
        self.root.after(2000, toast.destroy)

    def run(self):
        """Start the application"""
        self.root.mainloop()


if __name__ == "__main__":
    # Hide console window on Windows
    if sys.platform == 'win32':
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except:
            pass

    if not DND_AVAILABLE:
        print("\n" + "=" * 60)
        print("WARNING: Drag-and-drop support not available!")
        print("Please install: pip install tkinterdnd2")
        print("=" * 60 + "\n")

    app = AlwaysOnTopClipboard()
    app.run()
