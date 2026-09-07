"""Локальный CLI-интерфейс для общения с Маи."""
from __future__ import annotations

import logging
import random
from datetime import datetime

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    RICH = True
except ImportError:
    RICH = False

from mai.config import CREATOR_USER_ID, ensure_dirs
from mai.llm import generate_response, query_llm_raw
from mai.memory import (
    build_context, format_global_memory_for_prompt,
    format_memory_for_prompt, start_memory_thread,
)
from mai.prompts import RESPONSE_PROMPT, THINK_PROMPT
from mai.storage import (
    clear_chat, create_chat, get_recent_history,
    load_global_memory, update_chat,
)
from mai.tools import choose_action
from mai.utils.text import clean_reply

logger = logging.getLogger(__name__)

CLI_CREATOR_ID = CREATOR_USER_ID
CLI_GUEST_ID = 999999


class MaiCLI:
    def __init__(self, as_creator: bool = True):
        self.console = Console() if RICH else None
        self.as_creator = as_creator
        self.user_id = CLI_CREATOR_ID if as_creator else CLI_GUEST_ID
        self.username = "Sakair1" if as_creator else "Guest"
        self.chat_id = f"cli_{self.user_id}"

    def print_banner(self):
        mode = "👑 Создатель (Sakair1)" if self.as_creator else "👤 Гость"
        text = (
            f"🐱 Mai CLI\n"
            f"Режим: {mode}\n"
            f"Команды: /clear /memory /stats /switch /exit\n"
            + "─" * 60
        )
        if self.console:
            self.console.print(Panel(text, border_style="magenta"))
        else:
            print(text)

    def print_user(self, text: str):
        if self.console:
            self.console.print(f"[bold blue]{self.username}[/] [dim]»[/] {text}")
        else:
            print(f"{self.username} » {text}")

    def print_mai(self, text: str):
        if self.console:
            self.console.print(f"[bold magenta]Маи[/] [dim]»[/] {text}")
        else:
            print(f"Маи » {text}")

    def print_sys(self, text: str, style: str = "yellow"):
        if self.console:
            self.console.print(f"[dim][ {text} ][/]", style=style)
        else:
            print(f"[ {text} ]")

    def handle_command(self, cmd: str) -> bool:
        cmd = cmd.lower().strip()
        if cmd in ("/exit", "/quit"):
            self.print_sys("Пока! 👋", "magenta")
            return True
        if cmd == "/clear":
            clear_chat(self.chat_id)
            create_chat(self.chat_id)
            self.print_sys("История очищена", "green")
            return True
        if cmd == "/memory":
            self._show_memory()
            return True
        if cmd == "/stats":
            self._show_stats()
            return True
        if cmd == "/switch":
            self.as_creator = not self.as_creator
            self.user_id = CLI_CREATOR_ID if self.as_creator else CLI_GUEST_ID
            self.username = "Sakair1" if self.as_creator else "Guest"
            self.chat_id = f"cli_{self.user_id}"
            create_chat(self.chat_id)
            self.print_sys(
                f"Режим: {'Создатель' if self.as_creator else 'Гость'}", "green"
            )
            return True
        if cmd == "/help":
            self.print_sys(
                "/clear — очистить\n/memory — память\n/stats — статистика\n"
                "/switch — сменить режим\n/exit — выход", "cyan"
            )
            return True
        return False

    def _show_memory(self):
        m = format_memory_for_prompt(self.chat_id, self.user_id, "")
        g = format_global_memory_for_prompt(self.user_id, is_creator=self.as_creator)
        content = f"=== Память чата ===\n{m or '(пусто)'}\n\n=== Глобальная ===\n{g or '(пусто)'}"
        if self.console:
            self.console.print(Panel(content, title="Memory", border_style="cyan"))
        else:
            print(content)

    def _show_stats(self):
        memory = load_global_memory()
        stats = memory.get("global_stats", {})
        content = (
            f"Уникальных: {stats.get('total_unique_users', 0)}\n"
            f"Обработано: {stats.get('total_messages_processed', 0)}\n"
            f"Самый активный: {stats.get('most_active_user', 'нет')}\n"
            f"Среднее: {stats.get('average_messages_per_user', 0)}"
        )
        if self.console:
            self.console.print(Panel(content, title="Stats", border_style="green"))
        else:
            print(content)

    def _think(self, context: str, user_message: str) -> str:
        prompt = THINK_PROMPT.format(context=context, user_message=user_message)
        raw = query_llm_raw(prompt, n_predict=80, temperature=0.7,
                            stop=["</Mai_thoughts>", "\n\n"])
        return clean_reply(raw) if raw else "обычное сообщение"

    def _generate_final(self, context: str, user_message: str, thought: str) -> str:
        prompt = RESPONSE_PROMPT.format(
            context=context, user_message=user_message, thought=thought
        )
        return generate_response(prompt)

    def chat_loop(self):
        ensure_dirs()
        create_chat(self.chat_id)
        self.print_banner()
        self.print_sys("Начни общение с Маи. Ctrl+C для выхода.", "dim")

        while True:
            try:
                if RICH:
                    user_text = Prompt.ask(f"[bold blue]{self.username}[/]")
                else:
                    user_text = input(f"{self.username} » ")

                user_text = user_text.strip()
                if not user_text:
                    continue
                if user_text.startswith("/") and self.handle_command(user_text):
                    if user_text in ("/exit", "/quit"):
                        break
                    continue

                update_chat(self.chat_id, self.username, user_text, user_id=self.user_id)
                self.print_user(user_text)

                memory_text = format_memory_for_prompt(self.chat_id, self.user_id, user_text)
                global_text = format_global_memory_for_prompt(self.user_id, is_creator=self.as_creator)
                history = get_recent_history(self.chat_id, 20)
                context = build_context(history, memory_text, global_text)
                context += f"\n\n<info>ID Sakair1: {CREATOR_USER_ID}. ID собеседника: {self.user_id}.</info>"

                self.print_sys("Маи думает...", "dim")

                # Pipeline
                thought = self._think(context, user_text)
                self.print_sys(f"[мысль] {thought}", "dim")

                action = choose_action(context, user_text, thought)
                self.print_sys(f"[действие] {action.type}", "dim")

                if action.type == "SILENCE":
                    self.print_sys("(промолчала)", "dim")
                elif action.type == "REACT":
                    self.print_mai(action.emoji)
                    update_chat(self.chat_id, "Mai", action.emoji, user_id=self.user_id)
                elif action.type == "MULTI":
                    for msg in action.messages or []:
                        self.print_mai(msg)
                        update_chat(self.chat_id, "Mai", msg, user_id=self.user_id)
                else:
                    reply = action.text if action.text and action.text != "..." \
                        else self._generate_final(context, user_text, thought)
                    self.print_mai(reply)
                    update_chat(self.chat_id, "Mai", reply, user_id=self.user_id)

                start_memory_thread(self.chat_id, self.user_id, self.username)

            except KeyboardInterrupt:
                self.print_sys("\nВыход...", "dim")
                break
            except Exception as e:
                logger.exception("CLI error")
                self.print_sys(f"Ошибка: {e}", "red")


def run_cli():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    )

    if RICH:
        console = Console()
        console.print("\n[bold magenta]🐱 Mai CLI[/]\n")
        console.print("[1] Sakair1 (создатель)")
        console.print("[2] Гость\n")
        choice = Prompt.ask("Выбор", choices=["1", "2"], default="1")
    else:
        print("\n🐱 Mai CLI\n[1] Sakair1\n[2] Гость\n")
        choice = input("Выбор (1/2): ").strip() or "1"

    app = MaiCLI(as_creator=(choice == "1"))
    app.chat_loop()