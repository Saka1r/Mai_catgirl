"""Локальный CLI-интерфейс для общения с Маи."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.prompt import Prompt
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from mai.config import CREATOR_USER_ID, ensure_dirs
from mai.llm import ask_llama
from mai.memory import (
    build_context,
    format_global_memory_for_prompt,
    format_memory_for_prompt,
    start_memory_thread,
)
from mai.storage import (
    clear_chat,
    create_chat,
    get_recent_history,
    load_global_memory,
    update_chat,
)

logger = logging.getLogger(__name__)

# Константы CLI-сессии
CLI_CHAT_ID = "cli_session"
CLI_USER_ID_CREATOR = CREATOR_USER_ID
CLI_USER_ID_GUEST = 999999  # Виртуальный ID для тестового гостя


class MaiCLI:
    """Основной класс CLI-приложения."""

    def __init__(self, as_creator: bool = True):
        self.console = Console() if RICH_AVAILABLE else None
        self.as_creator = as_creator
        self.user_id = CLI_USER_ID_CREATOR if as_creator else CLI_USER_ID_GUEST
        self.username = "Sakair1" if as_creator else "Guest"
        self.chat_id = f"cli_{self.user_id}"

    def print_banner(self) -> None:
        banner = Text()
        banner.append("🐱 Mai CLI\n", style="bold magenta")
        banner.append(f"Режим: {'👑 Создатель (Sakair1)' if self.as_creator else '👤 Гость'}\n", style="cyan")
        banner.append("Команды: ", style="dim")
        banner.append("/clear /memory /stats /whoami /switch /exit\n", style="yellow")
        banner.append("─" * 60, style="dim")

        if self.console:
            self.console.print(Panel(banner, border_style="magenta"))
        else:
            print(str(banner))

    def print_user_message(self, text: str) -> None:
        if self.console:
            self.console.print(f"[bold blue]{self.username}[/] [dim]»[/] {text}")
        else:
            print(f"{self.username} » {text}")

    def print_mai_message(self, text: str) -> None:
        if self.console:
            self.console.print(f"[bold magenta]Маи[/] [dim]»[/] {text}")
        else:
            print(f"Маи » {text}")

    def print_system(self, text: str, style: str = "yellow") -> None:
        if self.console:
            self.console.print(f"[dim][ {text} ][/]", style=style)
        else:
            print(f"[ {text} ]")

    def handle_command(self, command: str) -> bool:
        """Обрабатывает slash-команды. Возвращает True если команда обработана."""
        cmd = command.lower().strip()

        if cmd == "/exit" or cmd == "/quit":
            self.print_system("Пока! 👋", "magenta")
            return True

        if cmd == "/clear":
            clear_chat(self.chat_id)
            create_chat(self.chat_id)
            self.print_system("История очищена", "green")
            return True

        if cmd == "/memory":
            self._show_memory()
            return True

        if cmd == "/stats":
            self._show_stats()
            return True

        if cmd == "/whoami":
            self.print_system(
                f"Ты: {self.username} (ID: {self.user_id})",
                "cyan",
            )
            return True

        if cmd == "/switch":
            self.as_creator = not self.as_creator
            self.user_id = CLI_USER_ID_CREATOR if self.as_creator else CLI_USER_ID_GUEST
            self.username = "Sakair1" if self.as_creator else "Guest"
            self.chat_id = f"cli_{self.user_id}"
            create_chat(self.chat_id)
            self.print_system(
                f"Переключено на: {'Создатель' if self.as_creator else 'Гость'}",
                "green",
            )
            return True

        if cmd == "/help":
            self.print_system(
                "/clear — очистить историю\n"
                "/memory — показать память\n"
                "/stats — статистика\n"
                "/whoami — кто ты\n"
                "/switch — сменить режим (создатель/гость)\n"
                "/exit — выход",
                "cyan",
            )
            return True

        return False

    def _show_memory(self) -> None:
        memory_text = format_memory_for_prompt(self.chat_id, self.user_id)
        global_text = format_global_memory_for_prompt(
            self.user_id, is_creator=self.as_creator
        )

        content = Text()
        content.append("=== Память чата ===\n", style="bold cyan")
        content.append(memory_text or "(пусто)", style="white")
        content.append("\n\n=== Глобальная память ===\n", style="bold cyan")
        content.append(global_text or "(пусто)", style="white")

        if self.console:
            self.console.print(Panel(content, title="Memory", border_style="cyan"))
        else:
            print(str(content))

    def _show_stats(self) -> None:
        memory = load_global_memory()
        stats = memory.get("global_stats", {})
        users_count = len(memory.get("users_index", {}))

        content = (
            f"Уникальных пользователей: {stats.get('total_unique_users', 0)}\n"
            f"Обработано сообщений: {stats.get('total_messages_processed', 0)}\n"
            f"Пользователей в индексе: {users_count}\n"
            f"Самый активный: {stats.get('most_active_user', 'нет')}\n"
            f"Среднее сообщений/пользователь: {stats.get('average_messages_per_user', 0)}"
        )

        if self.console:
            self.console.print(Panel(content, title="Stats", border_style="green"))
        else:
            print(content)

    def chat_loop(self) -> None:
        """Основной цикл общения."""
        ensure_dirs()
        create_chat(self.chat_id)
        self.print_banner()
        self.print_system("Начни общение с Маи. Ctrl+C для выхода.", "dim")

        while True:
            try:
                if RICH_AVAILABLE:
                    user_text = Prompt.ask(f"[bold blue]{self.username}[/]")
                else:
                    user_text = input(f"{self.username} » ")

                user_text = user_text.strip()
                if not user_text:
                    continue

                # Slash-команды
                if user_text.startswith("/"):
                    if self.handle_command(user_text):
                        if user_text in ("/exit", "/quit"):
                            break
                        continue

                # Сохраняем и показываем
                update_chat(self.chat_id, self.username, user_text, user_id=self.user_id)
                #self.print_user_message(user_text)

                # Генерируем ответ
                memory_text = format_memory_for_prompt(self.chat_id, self.user_id)
                global_text = format_global_memory_for_prompt(
                    self.user_id, is_creator=self.as_creator
                )
                history = get_recent_history(self.chat_id, 20)
                context = build_context(history, memory_text, global_text)

                self.print_system("Маи печатает...", "dim")
                reply = ask_llama(context, user_text)

                self.print_mai_message(reply)
                update_chat(self.chat_id, "Mai", reply, user_id=self.user_id)

                # Фоновый анализ памяти
                start_memory_thread(self.chat_id, self.user_id)

            except KeyboardInterrupt:
                self.print_system("\nВыход...", "dim")
                break
            except Exception as e:
                logger.exception("CLI error: %s", e)
                self.print_system(f"Ошибка: {e}", "red")


def run_cli() -> None:
    """Запуск CLI с выбором режима."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    )

    if RICH_AVAILABLE:
        console = Console()
        console.print("\n[bold magenta]🐱 Mai CLI[/]\n")
        console.print("[1] Войти как Sakair1 (создатель)")
        console.print("[2] Войти как гость (тестовый режим)\n")
        choice = Prompt.ask("Выбор", choices=["1", "2"], default="1")
    else:
        print("\n🐱 Mai CLI\n")
        print("[1] Войти как Sakair1 (создатель)")
        print("[2] Войти как гость (тестовый режим)\n")
        choice = input("Выбор (1/2): ").strip() or "1"

    app = MaiCLI(as_creator=(choice == "1"))
    app.chat_loop()
