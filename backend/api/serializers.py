import base64
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework import serializers
from djoser.serializers import UserSerializer
from recipes.models import Ingredient, RecipeIngredient, Recipe
from users.models import User, Subscription


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith("data:image"):
            format, imgstr = data.split(";base64,")
            ext = format.split("/")[-1]
            data = ContentFile(base64.b64decode(imgstr), name="temp." + ext)
        return super().to_internal_value(data)


class AvatarUpdateSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=True)

    class Meta:
        model = User
        fields = ('avatar',)


class UserMeSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name',
            'last_name', 'email', 'is_subscribed', 'avatar'
        )

    def get_is_subscribed(self, obj):
        return False

    def get_avatar(self, obj):
        if obj.avatar:
            return obj.avatar.url
        return None


class CustomUserCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания пользователя с дополнительными полями"""

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name',
                  'last_name', 'password')
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password']
        )
        return user


class UserProfileSerializer(UserSerializer):
    """Сериализатор для профиля пользователя с подписками"""
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
            "avatar",
        )
        extra_kwargs = {
            "email": {"required": True},
            "username": {"required": True},
            "first_name": {"required": True, "allow_blank": False},
            "last_name": {"required": True, "allow_blank": False},
        }

    def get_is_subscribed(self, user_profile):
        request = self.context.get("request")
        return (
            request is not None
            and request.user.is_authenticated
            and Subscription.objects.filter(
                user=request.user,
                author=user_profile
            ).exists()
        )


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
        request = self.context.get("request")
        recipes_limit = request.GET.get("recipes_limit") if request else None
        queryset = user_obj.recipes.all()
        if recipes_limit:
            try:
                queryset = queryset[:int(recipes_limit)]
            except ValueError:
                pass
        return RecipeShortSerializer(
            queryset,
            many=True,
            context={"request": request}
        ).data


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для ингредиентов"""
    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")


class RecipeShortSerializer(serializers.ModelSerializer):
    """Сериализатор для краткого отображения рецепта"""
    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")
        read_only_fields = fields

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения ингредиентов в рецепте"""
    id = serializers.IntegerField(source="ingredient.id")
    name = serializers.CharField(source="ingredient.name")
    measurement_unit = serializers.CharField(
        source="ingredient.measurement_unit"
    )

    class Meta:
        model = RecipeIngredient
        fields = ("id", "name", "measurement_unit", "amount")


class RecipeIngredientWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи ингредиентов в рецепте"""
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source="ingredient",
    )
    amount = serializers.IntegerField(
        min_value=1,
        error_messages={"min_value": "Количество не может быть меньше 1"}
    )

    class Meta:
        model = RecipeIngredient
        fields = ("id", "amount")


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения полной информации о рецепте"""
    author = UserProfileSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        many=True,
        source="recipe_ingredients"
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
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
        read_only_fields = fields

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def _check_relation(self, obj, relation_name):
        request = self.context.get('request')
        return (
            request
            and request.user.is_authenticated
            and getattr(obj, relation_name).filter(user=request.user).exists()
        )

    def get_is_favorited(self, obj):
        return self._check_relation(obj, "favorited_by")

    def get_is_in_shopping_cart(self, obj):
        return self._check_relation(obj, "in_shopping_carts")


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания/обновления рецепта"""
    ingredients = RecipeIngredientWriteSerializer(many=True, allow_empty=False)
    image = Base64ImageField(required=True)
    cooking_time = serializers.IntegerField(min_value=1)

    class Meta:
        model = Recipe
        fields = (
            "ingredients",
            "image",
            "name",
            "text",
            "cooking_time",
        )

    def validate_ingredients(self, ingredients_data):
        if not ingredients_data:
            raise serializers.ValidationError(
                "Требуется хотя бы один ингредиент"
            )

        ingredient_ids = [item["ingredient"].id for item in ingredients_data]

        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                "Ингредиенты не должны повторяться"
            )

        existing_ids = Ingredient.objects.filter(
            id__in=ingredient_ids
        ).values_list('id', flat=True)
        missing_ids = set(ingredient_ids) - set(existing_ids)
        if missing_ids:
            raise serializers.ValidationError(
                f"Ингредиенты с ID {missing_ids} не существуют"
            )

        return ingredients_data

    @transaction.atomic
    def _create_ingredients(self, recipe, ingredients_data):
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient_data["ingredient"],
                amount=ingredient_data["amount"],
            )
            for ingredient_data in ingredients_data
        ])

    def validate(self, attrs):
        request = self.context.get("request")
        if request and request.method in ['PATCH', 'PUT']:
            if 'ingredients' not in self.initial_data:
                raise serializers.ValidationError({
                    'ingredients': ['Это поле обязательно.']
                })
        return super().validate(attrs)

    @transaction.atomic
    def create(self, validated_data):
        ingredients_data = validated_data.pop("ingredients")
        recipe = Recipe.objects.create(
            author=self.context["request"].user,
            **validated_data
        )
        self._create_ingredients(recipe, ingredients_data)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop("ingredients", None)

        instance = super().update(instance, validated_data)

        if ingredients_data is not None:
            instance.ingredients.clear()
            self._create_ingredients(instance, ingredients_data)
        return instance

    def to_representation(self, instance):
        return RecipeReadSerializer(
            instance,
            context=self.context
        ).data


class SubscriptionSerializer(UserWithRecipesSerializer):
    """Сериализатор для подписок"""
    def get_is_subscribed(self, obj):
        return True
