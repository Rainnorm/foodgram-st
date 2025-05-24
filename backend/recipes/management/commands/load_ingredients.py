import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Загрузка ингредиентов из JSON файла в базу данных'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='ingredients.json',
            help='Название JSON файла в папке data (ingredients.json)'
        )

    def handle(self, *args, **options):
        file_name = options['file']
        data_dir = os.path.join(settings.BASE_DIR, 'data')
        file_path = os.path.join(data_dir, file_name)
        if not self._check_file_exists(file_path):
            return
        try:
            data = self._load_json_file(file_path)
            created_count = self._process_ingredients(data)
            self._print_success_message(created_count)
        except json.JSONDecodeError:
            self._print_error(
                f"Ошибка: Файл {file_name} содержит невалидный JSON")
        except Exception as e:
            self._print_error(f"Неожиданная ошибка: {str(e)}")

    def _check_file_exists(self, file_path):
        if not os.path.exists(file_path):
            self._print_error(f"Файл не найден: {file_path}")
            return False
        return True

    def _load_json_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _process_ingredients(self, data):
        created_count = 0
        for item in data:
            _, created = Ingredient.objects.get_or_create(
                name=item['name'],
                measurement_unit=item['measurement_unit']
            )
            if created:
                created_count += 1
        return created_count

    def _print_success_message(self, count):
        message = (
            f"Успешно загружено {count} ингредиентов"
            if count > 0
            else "Новых ингредиентов не добавлено (все уже существуют)"
        )
        self.stdout.write(self.style.SUCCESS(message))

    def _print_error(self, message):
        self.stdout.write(self.style.ERROR(message))
