import json
from django.core.management.base import BaseCommand
from recipes.models import Ingredient
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Load ingredients data from JSON file'

    def handle(self, *args, **options):
        file_path = os.path.join(settings.BASE_DIR, 'data', 'ingredients.json')

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                created_count = 0
                for item in data:
                    Ingredient.objects.get_or_create(
                        name=item['name'],
                        measurement_unit=item['measurement_unit']
                    )
                    created_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully loaded {created_count} ingredients'
                    )
                )
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(
                    'File ingredients.json not found in data directory')
            )
        except KeyError as e:
            self.stdout.write(
                self.style.ERROR(f'Key error in JSON data: {e}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error loading data: {e}')
            )
