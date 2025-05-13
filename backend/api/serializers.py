from recipes.models import Ingredient, RecipeIngredient, Recipe
from django.core.files.base import ContentFile
from djoser.serializers import UserSerializer
from rest_framework import serializers
from django.db import transaction
import base64
from users.models import User


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith("data:image"):
            if data.startswith("data:image"):
                format, imgstr = data.split(";base64,")
                ext = format.split("/")[-1]
                data = ContentFile(
                    base64.b64decode(imgstr), name="temp." + ext
                )

        return super().to_internal_value(data)


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления ингредиентов"""

    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")


class UserProfileSerializer(UserSerializer):
    """Сериализатор для профиля пользователя"""

    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "password",
            "is_subscribed",
            "avatar",
        )
        extra_kwargs = {
            "email": {"required": True},
            "username": {"required": True},
            "password": {"required": True, "write_only": True},
            "first_name": {"required": True, "allow_blank": False},
            "last_name": {"required": True, "allow_blank": False},
        }

    def get_is_subscribed(self, user_profile):
        request = self.context.get("request")
        return (
            request is not None
            and not request.user.is_anonymous
            and request.user.is_authenticated
            and user_profile.followers.filter(user=request.user).exists()
        )

    def get_avatar(self, user_profile):
        if user_profile.avatar:
            return user_profile.avatar.url
        return None


class RecipeShortSerializer(serializers.ModelSerializer):
    """Сериализатор для получения краткой информации о рецептах"""

    class Meta:
        model = Recipe
        read_only_fields = ("id", "name", "image", "cooking_time")
        fields = read_only_fields


class UserWithRecipesSerializer(UserProfileSerializer):
    """Сериализатор для пользователя с его рецептами"""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source="recipes.count", read_only=True
    )

    class Meta(UserProfileSerializer.Meta):
        fields = (
            *UserProfileSerializer.Meta.fields,
            "recipes",
            "recipes_count",
        )

    def get_recipes(self, user_obj):
        return RecipeShortSerializer(
            user_obj.recipes.all()[
                : int(
                    self.context.get("request").GET.get(
                        "recipes_limit", 10**10
                    )
                )
            ],
            many=True,
        ).data


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения рецептов ингредиентов"""

    id = serializers.IntegerField(source="ingredient.id")
    name = serializers.CharField(source="ingredient.name")
    measurement_unit = serializers.CharField(
        source="ingredient.measurement_unit"
    )

    class Meta:
        model = RecipeIngredient
        fields = ("id", "name", "measurement_unit", "amount")


class RecipeIngredientWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для написания рецептов ингредиентов"""

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source="ingredient",
    )
    amount = serializers.IntegerField(
        required=True,
        min_value=1,
    )

    class Meta:
        model = RecipeIngredient
        fields = ("id", "amount")


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для считывания сведений о рецепте."""

    author = UserProfileSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        many=True, read_only=True, source="recipe_ingredients"
    )
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        read_only_fields = (
            "id",
            "author",
            "ingredients",
            "is_favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "text",
            "cooking_time",
        )
        fields = read_only_fields

    def _get_exists_relation(self, recipe_obj, relation_name):
        request = self.context.get("request")
        return (
            request
            and request.user.is_authenticated
            and getattr(recipe_obj, relation_name)
            .filter(user=request.user)
            .exists()
        )

    def get_is_favorited(self, recipe_obj):
        return self._get_exists_relation(recipe_obj, "favoriterecipes")

    def get_is_in_shopping_cart(self, recipe_obj):
        return self._get_exists_relation(recipe_obj, "shoppingcarts")


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи сведений о рецепте"""

    ingredients = RecipeIngredientWriteSerializer(many=True, required=True)
    image = Base64ImageField()
    cooking_time = serializers.IntegerField(min_value=1)

    class Meta:
        model = Recipe
        fields = (
            "id",
            "ingredients",
            "image",
            "name",
            "text",
            "cooking_time",
        )

    def validate_ingredients(self, ingredients_data):
        if not ingredients_data:
            raise serializers.ValidationError(
                {"ingredients": "Cannot be empty."}
            )

        ingredient_ids = [item["ingredient"] for item in ingredients_data]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                {"ingredients": "Cannot contain duplicates."}
            )

        return ingredients_data

    def validate(self, data):
        if self.instance and "ingredients" not in data:
            raise serializers.ValidationError(
                {"ingredients": "This field is required."}
            )
        return data

    def _create_recipe_ingredients(self, recipe, ingredients_data):
        RecipeIngredient.objects.bulk_create(
            [
                RecipeIngredient(
                    recipe=recipe,
                    ingredient=ingredient_data["ingredient"],
                    amount=ingredient_data["amount"],
                )
                for ingredient_data in ingredients_data
            ]
        )

    @transaction.atomic
    def create(self, validated_data):
        ingredients_data = validated_data.pop("ingredients")
        recipe = super().create(validated_data)
        self._create_recipe_ingredients(recipe, ingredients_data)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop("ingredients")
        instance.recipe_ingredients.all().delete()
        self._create_recipe_ingredients(instance, ingredients_data)
        return super().update(instance, validated_data)

    def to_representation(self, recipe):
        return RecipeReadSerializer(recipe, context=self.context).data
