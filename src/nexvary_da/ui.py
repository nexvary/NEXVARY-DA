from __future__ import annotations

from pathlib import Path


def launch_ui(root: str | Path) -> None:
    import tkinter as tk

    from .ui_app import DeveloperAgentUI

    window = tk.Tk()
    window.withdraw()
    app = DeveloperAgentUI(window, root)
    window.protocol("WM_DELETE_WINDOW", app.close)
    window.update_idletasks()
    window.deiconify()
    window.lift()
    window.mainloop()
