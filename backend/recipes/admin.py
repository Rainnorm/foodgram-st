from django.contrib import admin
from users.models import User, Subscription
from .models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    FavoriteRecipe,
    ShoppingCart
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email',
                    'recipes_count', 'followers_count', 'following_count')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    filter_horizontal = ('groups', 'user_permissions')

    def recipes_count(self, obj):
        return obj.recipes.count()
    recipes_count.short_description = 'Рецепты'

    def followers_count(self, obj):
        return obj.authors.count()
    followers_count.short_description = 'Подписчики'

    def following_count(self, obj):
        return obj.followers.count()
    following_count.short_description = 'Подписки'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'user')
    search_fields = ('author__username', 'user__username')


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'author', 'cooking_time',
                    'favorites_count')
    search_fields = ('name', 'author__username')
    list_filter = ('author',)
    inlines = (RecipeIngredientInline,)

    def favorites_count(self, obj):
        return obj.favoriterecipes.count()
    favorites_count.short_description = 'В избранном'


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_unit', 'recipes_count')
    search_fields = ('name', 'measurement_unit')

    def recipes_count(self, obj):
        return obj.recipes.count()
    recipes_count.short_description = 'Используется в рецептах'


@admin.register(FavoriteRecipe)
class FavoriteRecipeAdmin(admin.ModelAdmin):
    list_display = ('user', 'recipe')
    search_fields = ('user__username', 'recipe__name')


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('user', 'recipe')
    search_fields = ('user__username', 'recipe__name')
