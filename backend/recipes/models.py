from django.db import models
from django.core.validators import MinValueValidator
from users.models import User
# Create your models here.


class Ingredient(models.Model):
    """Модель ингредиента"""
    name = models.CharField(verbose_name='Название', max_length=256)
    measurement_unit = models.CharField(max_length=256)

    class Meta:
        ordering = ("name",)
        verbose_name = "ингредиент"
        verbose_name_plural = "ингредиенты"
        constraints = [models.UniqueConstraint(
            fields=["name", "measurement_unit"],
            name="unique_ingredient")]

    def __str__(self):
        return f"{self.name} - {self.measurement_unit}"


class Recipe(models.Model):
    """Модель рецепта"""
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="recipes",
        verbose_name="Автор")
    name = models.CharField(
        max_length=256,
        verbose_name="Название")
    image = models.ImageField(
        upload_to="recipes/images/",
        verbose_name="Изображение")
    text = models.TextField(verbose_name="Описание")
    ingredients = models.ManyToManyField(
        Ingredient,
        through="RecipeIngredient",
        related_name="recipes")
    cooking_time = models.PositiveIntegerField(
        verbose_name="Время приготовления (мин)",
        validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"
        ordering = ["-id"]

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    """Промежуточная модель между рецептом и ингредиентом"""
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
        related_name="recipe_ingredients")
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        verbose_name='Ингредиент')
    amount = models.PositiveIntegerField(
        verbose_name='Количество',
        validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "Ингредиент рецепта"
        verbose_name_plural = "Ингредиенты рецепта"

    def __str__(self):
        return f"{self.ingredient} — {self.recipe}"


class FavoriteRecipe(models.Model):
    """Модель избранного рецепта"""
    user = models.ForeignKey(
        User,
        verbose_name='Пользователь',
        related_name='favorites',
        on_delete=models.CASCADE)
    recipe = models.ForeignKey(
        Recipe,
        verbose_name='Рецепт',
        related_name='favorited_by',
        on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Избранный рецепт"
        verbose_name_plural = "Избранные рецепты"


class ShoppingCart(models.Model):
    """Модель списка покупок"""
    user = models.ForeignKey(
        User,
        verbose_name='Пользователь',
        related_name='shopping_carts',
        on_delete=models.CASCADE)
    recipe = models.ForeignKey(
        Recipe,
        verbose_name='Рецепт',
        related_name='in_shopping_carts',
        on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Рецепт в списке покупок"
        verbose_name_plural = "Рецепты в списке покупок"
