from django.shortcuts import redirect, get_object_or_404
from .models import Recipe


def redirect_to_recipe(request, recipe_id):
    """Редирект на рецепт"""
    get_object_or_404(Recipe, id=recipe_id)
    return redirect('recipes:detail', recipe_id=recipe_id)
