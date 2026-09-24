from __future__ import annotations

import webbrowser
from typing import Callable

from .ui_theme import PALETTE


SOCIAL_LINKS: tuple[tuple[str, str], ...] = (
    ("Website", "https://nexvary.com/"),
    ("Facebook", "https://www.facebook.com/share/14p9krEn5ij/"),
    ("Email", "mailto:info@nexvary.com"),
    ("YouTube", "https://www.youtube.com/@NexvaryInc"),
    ("X", "https://x.com/Nexvary"),
)


SYSTEM_SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Easy Mode", PALETTE.cyan, (
        "Goal-first home screen for common work without terminal commands.",
        "Automatic Native/Hybrid engine choice for normal task planning.",
        "One-click Build & Test, Release Check, Add Project, Tool Box, and setup.",
    )),
    ("AI & Agent Orchestration", PALETTE.purple, (
        "NEXVARY Native, ZCode plan-only, and Hybrid agent modes.",
        "Cloud reasoning can plan while NEXVARY remains the local execution authority.",
        "Machine plans are validated through NEXVARY tools and permissions before execution.",
    )),
    ("Projects & Persistent Work", PALETTE.gold, (
        "Safe GitHub project import with clone reuse and toolchain detection.",
        "Persistent project state, checkpoints, events, terminals, processes, and resume data.",
        "Workspace Guard constrains file, shell, Git, network, ADB, release, and desktop permissions.",
    )),
    ("Build, Test & Release", PALETTE.blue, (
        "Python, Gradle/Android, Node, and CMake build profiles.",
        "Engineer and strict Release Gate modes with build, tests, lint/static checks, artifacts and SHA-256 evidence.",
        "Native Windows executable/installer and Linux native/Debian packaging in CI.",
    )),
    ("UI, Navigation & Quality", PALETTE.magenta, (
        "Runtime UI probe checks clipping, overlap, tiny targets, missing callbacks, and screenshot evidence.",
        "Navigation Integrity Probe opens every registered window, tab, and subpage.",
        "Static QA covers dead links, orphan HTML, Tk buttons, localization, RTL signals, and workspace health.",
    )),
    ("Security", PALETTE.orange, (
        "Secret-pattern scan, Python AST source audit, dependency vulnerability audit, and fail-closed permissions.",
        "External integrations do not automatically gain execution rights or silently install themselves.",
        "Sensitive API keys remain session-only where supported and are excluded from persistent settings.",
    )),
    ("Desktop & Browser Automation", PALETTE.cyan, (
        "Cua Driver adapter for desktop inspection and explicitly approved computer-use mutations.",
        "Oya Browser integration for browser tasks and reusable playbooks.",
        "Graphical Tool Box forms keep normal workflows out of the command line.",
    )),
    ("Media & MCP", PALETTE.yellow, (
        "FastMCP gateway for approved MCP servers and tools.",
        "VoiceStudio external-service integration for voice workflows.",
        "Video Studio provides a guided 60-second workflow with MoneyPrinterTurbo plus free local alternatives.",
        "Optional Qwen-Image 2.1 image runtime remains available for image workflows.",
    )),
    ("Android & GitHub", PALETTE.blue, (
        "Android SDK/Gradle/ADB environment detection, build/test/lint/device operations behind explicit permissions.",
        "GitHub repository, pull request, workflow, artifact, and release integration.",
        "CI remains an independent final verification layer after local work.",
    )),
    ("Advanced Mode", PALETTE.silver_bright, (
        "Engineering control panel with agent pool, work modes, evidence timeline, permissions, and persistent terminal.",
        "Advanced controls remain optional; Easy Mode is the normal-user path.",
    )),
)


class _InfoWindow:
    def __init__(self, parent, *, title: str, font_family: str, scale: float):
        import tkinter as tk
        self.tk = tk
        self.font = font_family
        self.scale = scale
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.configure(bg=PALETTE.background)
        self.window.geometry(f"{self.px(940)}x{self.px(720)}")
        self.window.minsize(self.px(780), self.px(580))
        self.window.transient(parent)

    def px(self, value: int) -> int:
        return max(1, int(round(value * self.scale)))

    def label(self, parent, text: str, *, size=9, fg=None, bold=False):
        return self.tk.Label(
            parent, text=text, bg=parent.cget("bg"), fg=fg or PALETTE.text,
            justify="left", anchor="w",
            wraplength=self.px(800),
            font=(self.font, self.px(size), "bold" if bold else "normal"),
        )

    def button(self, parent, text: str, command: Callable[[], object], *, accent=False):
        return self.tk.Button(
            parent, text=text, command=command,
            bg=PALETTE.action if accent else PALETTE.surface_alt,
            fg=PALETTE.background if accent else PALETTE.action,
            activebackground=PALETTE.action_hover,
            activeforeground=PALETTE.background,
            relief="flat", bd=0, cursor="hand2",
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            highlightcolor=PALETTE.silver_bright,
            padx=self.px(12), pady=self.px(7),
            font=(self.font, self.px(8), "bold"),
        )

    def _header(self, title: str, subtitle: str, color: str):
        top = self.tk.Frame(
            self.window, bg=PALETTE.surface,
            highlightbackground=PALETTE.silver, highlightthickness=1,
        )
        top.pack(fill="x")
        self.tk.Frame(top, bg=color, height=self.px(3)).pack(fill="x")
        self.label(top, title, size=17, fg=color, bold=True).pack(
            anchor="w", padx=self.px(20), pady=(self.px(14), self.px(2))
        )
        self.label(top, subtitle, size=8, fg=PALETTE.muted).pack(
            anchor="w", padx=self.px(20), pady=(0, self.px(14))
        )

    def _scroll_body(self):
        canvas = self.tk.Canvas(self.window, bg=PALETTE.background, highlightthickness=0, bd=0)
        scrollbar = self.tk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        body = self.tk.Frame(canvas, bg=PALETTE.background)
        body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(body_window, width=max(1, event.width)),
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        return body

    def close(self):
        self.window.destroy()


class AboutWindow(_InfoWindow):
    def __init__(self, parent, *, font_family: str, scale: float):
        super().__init__(parent, title="NEXVARY — About / عنا", font_family=font_family, scale=scale)
        self._header("ABOUT NEXVARY / عنا", "Official company information and social channels", PALETTE.cyan)
        body = self._scroll_body()

        identity = self.tk.Frame(body, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        identity.pack(fill="x", padx=self.px(18), pady=self.px(14))
        self.label(identity, "NEXVARY", size=19, fg=PALETTE.cyan, bold=True).pack(
            anchor="w", padx=self.px(18), pady=(self.px(16), self.px(2))
        )
        self.label(identity, "AI Engineering • Developer Automation • Security-Aware Local Execution",
                   size=9, fg=PALETTE.gold, bold=True).pack(anchor="w", padx=self.px(18))
        self.label(
            identity,
            "NEXVARY-DA makes complex engineering workflows usable through a guided graphical interface "
            "while preserving explicit local permissions, evidence-driven testing, and controlled automation.",
            size=9, fg=PALETTE.text,
        ).pack(anchor="w", fill="x", padx=self.px(18), pady=(self.px(10), self.px(16)))

        links = self.tk.Frame(body, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        links.pack(fill="x", padx=self.px(18), pady=(0, self.px(14)))
        self.label(links, "OFFICIAL LINKS / الروابط الرسمية", size=11, fg=PALETTE.magenta, bold=True).pack(
            anchor="w", padx=self.px(16), pady=(self.px(14), self.px(8))
        )
        accents = (PALETTE.cyan, PALETTE.blue, PALETTE.yellow, PALETTE.magenta, PALETTE.purple)
        for index, (name, url) in enumerate(SOCIAL_LINKS):
            row = self.tk.Frame(links, bg=PALETTE.surface_alt)
            row.pack(fill="x", padx=self.px(14), pady=self.px(3))
            accent = accents[index]
            self.tk.Frame(row, bg=accent, width=self.px(4)).pack(side="left", fill="y")
            self.label(row, name, size=9, fg=accent, bold=True).pack(side="left", padx=self.px(10), pady=self.px(8))
            self.label(row, url.replace("mailto:", ""), size=8, fg=PALETTE.muted).pack(
                side="left", fill="x", expand=True, padx=self.px(8)
            )
            self.button(row, "OPEN", lambda target=url: webbrowser.open(target), accent=True).pack(
                side="right", padx=self.px(8), pady=self.px(5)
            )

        actions = self.tk.Frame(body, bg=PALETTE.background)
        actions.pack(fill="x", padx=self.px(18), pady=(0, self.px(20)))
        self.button(actions, "BACK / رجوع", self.close, accent=True).pack(side="right")


class SystemOverviewWindow(_InfoWindow):
    def __init__(self, parent, *, font_family: str, scale: float):
        super().__init__(parent, title="NEXVARY — System Overview / حول النظام", font_family=font_family, scale=scale)
        self._header("SYSTEM OVERVIEW / حول النظام",
                     "Capabilities, security boundaries, and verification architecture", PALETTE.purple)
        body = self._scroll_body()

        intro = self.tk.Frame(body, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        intro.pack(fill="x", padx=self.px(18), pady=self.px(14))
        self.label(intro, "NEXVARY Developer Agent — AI Engineering & Computer Automation Platform",
                   size=12, fg=PALETTE.cyan, bold=True).pack(
            anchor="w", padx=self.px(16), pady=(self.px(14), self.px(4))
        )
        self.label(
            intro,
            "The platform combines cloud reasoning, local execution, build/test automation, desktop/browser tooling, "
            "media integrations, GitHub workflows, Android tooling, persistent project state, and release evidence "
            "behind one permission-controlled interface.",
            size=9, fg=PALETTE.text,
        ).pack(anchor="w", fill="x", padx=self.px(16), pady=(0, self.px(14)))

        for title, color, bullets in SYSTEM_SECTIONS:
            card = self.tk.Frame(body, bg=PALETTE.surface_alt,
                                 highlightbackground=PALETTE.silver, highlightthickness=1)
            card.pack(fill="x", padx=self.px(18), pady=self.px(5))
            self.tk.Frame(card, bg=color, height=self.px(3)).pack(fill="x")
            self.label(card, title, size=11, fg=color, bold=True).pack(
                anchor="w", padx=self.px(14), pady=(self.px(10), self.px(4))
            )
            for bullet in bullets:
                self.label(card, f"• {bullet}", size=8, fg=PALETTE.text).pack(
                    anchor="w", fill="x", padx=self.px(18), pady=self.px(2)
                )
            self.tk.Frame(card, bg=PALETTE.surface_alt, height=self.px(7)).pack(fill="x")

        note = self.tk.Frame(body, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        note.pack(fill="x", padx=self.px(18), pady=self.px(14))
        self.label(note, "VERIFICATION PRINCIPLE", size=10, fg=PALETTE.orange, bold=True).pack(
            anchor="w", padx=self.px(14), pady=(self.px(12), self.px(4))
        )
        self.label(
            note,
            "A successful CI/security scan means no blocking findings were detected by the configured checks. "
            "It is evidence of the tested state, not a claim that software can be proven to contain zero "
            "vulnerabilities under all future conditions.",
            size=8, fg=PALETTE.muted,
        ).pack(anchor="w", fill="x", padx=self.px(14), pady=(0, self.px(12)))

        actions = self.tk.Frame(body, bg=PALETTE.background)
        actions.pack(fill="x", padx=self.px(18), pady=(0, self.px(20)))
        self.button(actions, "BACK / رجوع", self.close, accent=True).pack(side="right")


def open_about_window(parent, *, font_family: str, scale: float) -> AboutWindow:
    return AboutWindow(parent, font_family=font_family, scale=scale)


def open_system_overview_window(parent, *, font_family: str, scale: float) -> SystemOverviewWindow:
    return SystemOverviewWindow(parent, font_family=font_family, scale=scale)
