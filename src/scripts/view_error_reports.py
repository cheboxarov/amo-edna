#!/usr/bin/env python3
"""
Скрипт для просмотра error отчетов.
Показывает последние ошибки из файлов логов.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any


class ErrorReportsViewer:
    """Класс для просмотра error отчетов"""

    def __init__(self, logs_dir: Path = Path("logs")):
        self.logs_dir = logs_dir
        self.errors_log = logs_dir / "errors.log"
        self.errors_json = logs_dir / "errors.json"

    def get_recent_errors(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Получить ошибки за последние N часов"""
        errors = []
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Читаем JSON ошибки
        if self.errors_json.exists():
            try:
                with open(self.errors_json, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                error_data = json.loads(line.strip())
                                error_time = datetime.fromisoformat(error_data['timestamp'].replace('Z', '+00:00'))
                                if error_time > cutoff_time:
                                    errors.append(error_data)
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                print(f"Ошибка чтения JSON файла: {e}")

        # Сортируем по времени (новые сверху)
        errors.sort(key=lambda x: x['timestamp'], reverse=True)
        return errors

    def print_error_summary(self, hours: int = 24) -> None:
        """Вывести сводку по ошибкам"""
        errors = self.get_recent_errors(hours)

        if not errors:
            print(f"✅ За последние {hours} часов ошибок не найдено!")
            return

        print(f"🚨 Найдено {len(errors)} ошибок за последние {hours} часов:")
        print("=" * 80)

        # Группируем ошибки по типам
        error_types = {}
        for error in errors:
            error_type = error.get('level', 'UNKNOWN')
            if error_type not in error_types:
                error_types[error_type] = []
            error_types[error_type].append(error)

        for error_type, type_errors in error_types.items():
            print(f"\n🔴 {error_type}: {len(type_errors)} ошибок")

            for error in type_errors[:5]:  # Показываем первые 5 каждой категории
                timestamp = error.get('timestamp', 'UNKNOWN')
                logger = error.get('logger', 'UNKNOWN')
                message = error.get('message', 'No message')[:100]

                print(f"  📅 {timestamp}")
                print(f"  📍 {logger}")
                print(f"  💬 {message}")
                print()

        if len(errors) > 5:
            print(f"... и ещё {len(errors) - 5} ошибок")

    def print_detailed_error(self, error_index: int = 0, hours: int = 24) -> None:
        """Вывести детальную информацию об ошибке"""
        errors = self.get_recent_errors(hours)

        if not errors:
            print("Ошибок не найдено!")
            return

        if error_index >= len(errors):
            print(f"Индекс {error_index} вне диапазона. Доступно {len(errors)} ошибок.")
            return

        error = errors[error_index]

        print("📋 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ ОБ ОШИБКЕ")
        print("=" * 80)

        for key, value in error.items():
            if key == 'exception' and value:
                print(f"{key.upper()}:")
                print(f"  {value}")
            else:
                print(f"{key.upper()}: {value}")

    def show_help(self) -> None:
        """Показать справку"""
        print("📊 ПРОСМОТР ERROR ОТЧЕТОВ")
        print("=" * 50)
        print("Использование:")
        print("  python view_error_reports.py summary [часы]  - сводка ошибок")
        print("  python view_error_reports.py detail [индекс] [часы]  - детальная ошибка")
        print("  python view_error_reports.py help  - эта справка")
        print()
        print("Примеры:")
        print("  python view_error_reports.py summary        # ошибки за 24 часа")
        print("  python view_error_reports.py summary 6      # ошибки за 6 часов")
        print("  python view_error_reports.py detail 0      # первая ошибка")
        print("  python view_error_reports.py detail 1 12   # вторая ошибка за 12 часов")


def main():
    viewer = ErrorReportsViewer()

    if len(sys.argv) < 2:
        viewer.print_error_summary()
        return

    command = sys.argv[1].lower()

    if command == "summary":
        hours = 24
        if len(sys.argv) > 2:
            try:
                hours = int(sys.argv[2])
            except ValueError:
                print("Ошибка: часы должны быть числом")
                return
        viewer.print_error_summary(hours)

    elif command == "detail":
        error_index = 0
        hours = 24

        if len(sys.argv) > 2:
            try:
                error_index = int(sys.argv[2])
            except ValueError:
                print("Ошибка: индекс должен быть числом")
                return

        if len(sys.argv) > 3:
            try:
                hours = int(sys.argv[3])
            except ValueError:
                print("Ошибка: часы должны быть числом")
                return

        viewer.print_detailed_error(error_index, hours)

    elif command == "help":
        viewer.show_help()

    else:
        print(f"Неизвестная команда: {command}")
        viewer.show_help()


if __name__ == "__main__":
    main()
