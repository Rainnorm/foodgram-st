from django.shortcuts import redirect
from django.core.exceptions import ValidationError
from .models import Recipe


def redirect_to_recipe(request, recipe_id):
    """Редирект на рецепт"""

    if not Recipe.objects.filter(id=recipe_id).exists():
        raise ValidationError(f"Рецепт с id={recipe_id} не существует")
    return redirect(f"/recipes/{recipe_id}/")
