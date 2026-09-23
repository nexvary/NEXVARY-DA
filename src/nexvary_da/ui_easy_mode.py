from __future__ import annotations

from .ui_theme import PALETTE


class EasyModePanel:
    """Low-cognitive-load home screen for common NEXVARY workflows."""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.tk = app.tk
        self.project_var = self.tk.StringVar(value="Project ready")
        self.tools_var = self.tk.StringVar(value="Checking tools…")
        self.last_var = self.tk.StringVar(value="No check has run yet")
        self.message_var = self.tk.StringVar(
            value="Choose what you want to do. NEXVARY will select the technical path for you."
        )
        self._build()
        self.refresh()

    def _action_card(self, parent, title: str, subtitle: str, button: str, command, *, accent=False):
        card = self.app.card(parent, PALETTE.surface_alt)
        self.app.label(card, title, size=11, bold=True, bg=PALETTE.surface_alt).pack(
            anchor="w", padx=self.app.px(14), pady=(self.app.px(12), self.app.px(2))
        )
        self.app.label(
            card,
            subtitle,
            size=8,
            fg=PALETTE.muted,
            bg=PALETTE.surface_alt,
        ).pack(anchor="w", padx=self.app.px(14))
        self.app.button(card, button, command, accent=accent).pack(
            anchor="w",
            padx=self.app.px(14),
            pady=(self.app.px(12), self.app.px(14)),
        )
        return card

    def _build(self):
        tk = self.tk
        hero = tk.Frame(self.parent, bg=PALETTE.surface)
        hero.pack(fill="x", padx=self.app.px(22), pady=(self.app.px(22), self.app.px(12)))
        self.app.label(hero, "What do you want NEXVARY to do?", size=18, fg=PALETTE.gold, bold=True).pack(anchor="w")
        self.app.label(
            hero,
            "No commands required. Start with the result you want, not the tool you need.",
            size=9,
            fg=PALETTE.muted,
        ).pack(anchor="w", pady=(self.app.px(3), 0))

        status = tk.Frame(self.parent, bg=PALETTE.surface)
        status.pack(fill="x", padx=self.app.px(22), pady=(0, self.app.px(12)))
        for index, (title, variable) in enumerate(
            (
                ("PROJECT", self.project_var),
                ("TOOLS", self.tools_var),
                ("LAST CHECK", self.last_var),
            )
        ):
            status.columnconfigure(index, weight=1)
            card = self.app.card(status, PALETTE.surface_alt)
            card.grid(row=0, column=index, sticky="nsew", padx=self.app.px(3))
            self.app.label(card, title, size=7, fg=PALETTE.muted, bold=True, bg=PALETTE.surface_alt).pack(
                anchor="w", padx=self.app.px(11), pady=(self.app.px(8), 0)
            )
            tk.Label(
                card,
                textvariable=variable,
                bg=PALETTE.surface_alt,
                fg=PALETTE.text,
                font=(self.app.font, self.app.px(9), "bold"),
                anchor="w",
            ).pack(fill="x", padx=self.app.px(11), pady=(0, self.app.px(9)))

        grid = tk.Frame(self.parent, bg=PALETTE.surface)
        grid.pack(fill="both", expand=True, padx=self.app.px(19), pady=self.app.px(2))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        cards = (
            self._action_card(
                grid,
                "Start a task",
                "Describe the goal in normal language. NEXVARY chooses the engine and creates the plan.",
                "DESCRIBE MY TASK",
                self.app.plan_task_easy,
                accent=True,
            ),
            self._action_card(
                grid,
                "Build & test",
                "Run the normal engineering checks without choosing commands or test frameworks.",
                "BUILD & TEST PROJECT",
                self.app.run_quick_check,
            ),
            self._action_card(
                grid,
                "Tools & integrations",
                "Connect desktop automation, browser, voice, image and video tools from one setup screen.",
                "OPEN SETUP CENTER",
                self.app.open_integrations,
            ),
            self._action_card(
                grid,
                "Add another project",
                "Clone or reuse a GitHub project and register it in the safe workspace.",
                "ADD PROJECT",
                self.app.add_project,
            ),
        )
        for index, card in enumerate(cards):
            card.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=self.app.px(4),
                pady=self.app.px(4),
            )

        footer = tk.Frame(self.parent, bg=PALETTE.surface)
        footer.pack(fill="x", padx=self.app.px(22), pady=(self.app.px(8), self.app.px(18)))
        message = tk.Label(
            footer,
            textvariable=self.message_var,
            bg=PALETTE.surface,
            fg=PALETTE.blue_bright,
            anchor="w",
            justify="left",
            wraplength=self.app.px(760),
            font=(self.app.font, self.app.px(8)),
        )
        message.pack(side="left", fill="x", expand=True)
        self.app.button(
            footer,
            "ADVANCED MODE",
            lambda: self.app.show_experience("advanced"),
        ).pack(side="right", padx=(self.app.px(8), 0))

    def set_message(self, text: str) -> None:
        self.message_var.set(text)

    def refresh(self) -> None:
        try:
            statuses = self.app.runtime.plugins().all_statuses()
            ready = sum(1 for item in statuses if item.ready)
            self.tools_var.set(f"{ready}/{len(statuses)} ready")
        except Exception:
            self.tools_var.set("Setup needs attention")
        changed = 0
        try:
            changed = len(self.app.runtime.git.changed_files())
        except Exception:
            pass
        self.project_var.set("Ready" if not changed else f"{changed} changed file(s)")
        last = self.app.runtime.state.get_meta("last_coordinator_run")
        if isinstance(last, dict):
            complete = last.get("complete") is True
            self.last_var.set("Passed" if complete else "Needs attention")
        else:
            self.last_var.set("Not run yet")
