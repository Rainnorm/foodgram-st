from .filters import IngredientFilter, RecipeFilter
from .serializers import (
    RecipeReadSerializer,
    RecipeWriteSerializer,
    RecipeShortSerializer,
    UserProfileSerializer,
    UserWithRecipesSerializer,
    IngredientSerializer)
from datetime import datetime
from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.http import Http404, FileResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from recipes.models import Recipe, FavoriteRecipe, ShoppingCart, Ingredient
from .permissions import IsAuthorOrReadOnly
from .pagination import SitePagination
from djoser.views import UserViewSet as DjoserUserViewSet
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from users.models import Subscription
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
import base64
import uuid
import os
User = get_user_model()


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Представление для получения списка ингредиентов и поиска по имени"""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filterset_class = IngredientFilter
    filter_backends = [DjangoFilterBackend]
    permission_classes = [AllowAny]
    pagination_class = None


class RecipeViewSet(viewsets.ModelViewSet):
    """Представление для операций над рецептами"""

    queryset = Recipe.objects.all()
    filter_backends = [DjangoFilterBackend]
    pagination_class = SitePagination
    filterset_class = RecipeFilter
    permission_classes = (IsAuthorOrReadOnly,)

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return RecipeReadSerializer
        return RecipeWriteSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(methods=["get"], detail=True, url_path="get-link")
    def get_link_to_recipe(self, request, pk):
        if not Recipe.objects.filter(pk=pk).exists():
            raise Http404

        return Response(
            {
                "short-link": request.build_absolute_uri(
                    reverse("recipes:short-link-redirect", args=[pk])
                )
            }
        )

    def _handle_recipe_relation(
        self,
        request,
        recipe_id,
        model_class,
        already_exists_message,
        not_found_message
    ):
        recipe = get_object_or_404(Recipe, pk=recipe_id)
        current_user = request.user

        if request.method == "POST":
            _, created = model_class.objects.get_or_create(
                user=current_user, recipe=recipe
            )

            if not created:
                raise ValidationError({"errors": already_exists_message})

            return Response(
                RecipeShortSerializer(recipe).data,
                status=status.HTTP_201_CREATED,
            )

        relation = model_class.objects.filter(
            user=current_user,
            recipe=recipe).first()
        if not relation:
            raise ValidationError({"errors": not_found_message})

        relation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        return self._handle_recipe_relation(
            request,
            pk,
            FavoriteRecipe,
            "Рецепт уже в избранном",
            "Рецепт не был в избранном",
        )

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
    )
    def shopping_cart(self, request, pk=None):
        return self._handle_recipe_relation(
            request,
            pk,
            ShoppingCart,
            "Рецепт уже в списке покупок",
            "Рецепт не был в списке покупок",
        )

    @action(
        detail=False, permission_classes=[IsAuthenticated], methods=["get"]
    )
    def download_shopping_cart(self, request):
        recipes = Recipe.objects.filter(shoppingcarts__user=request.user)

        if not recipes.exists():
            raise ValidationError({"errors": "Список покупок пуст"})

        ingredients = (
            recipes.values(
                "ingredients__name", "ingredients__measurement_unit"
            )
            .annotate(total_amount=Sum("recipe_ingredients__amount"))
            .order_by("ingredients__name")
        )

        current_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        shopping_list = [
            "Фудграм - Список покупок",
            f"Дата: {current_date} UTC",
            f"Пользователь: {request.user.username}",
            "",
            "Ингредиенты:",
        ]

        for i, ingredient in enumerate(ingredients, 1):
            shopping_list.append(
                f"{i}. {ingredient['ingredients__name'].title()} - "
                f"{ingredient['total_amount']} "
                f"{ingredient['ingredients__measurement_unit']}"
            )

        shopping_list.append("")
        shopping_list.append("Рецепты:")

        for recipe in recipes:
            shopping_list.append(
                f"- {recipe.name} (автор: {recipe.author.get_full_name()})"
            )

        shopping_list.append("")
        shopping_list.append(
            f"Фудграм - Ваш кулинарный помощник © {datetime.now().year}"
        )

        return FileResponse(
            ("\n".join(shopping_list)),
            as_attachment=True,
            filename="shopping_list.txt",
            content_type="text/plain; charset=utf-8",
        )


class UserViewSet(DjoserUserViewSet):
    """Представление для работы с пользователями"""

    queryset = User.objects.all().order_by('username')
    pagination_class = SitePagination
    serializer_class = UserProfileSerializer
    permission_classes = [AllowAny]

    @action(
        detail=False, methods=["get"], permission_classes=[IsAuthenticated]
    )
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        methods=["put", "delete"],
        detail=False,
        url_path="me/avatar",
        permission_classes=[IsAuthenticated],
    )
    def avatar(self, request):
        current_user = request.user
        if request.method == "PUT":
            avatar_data = request.data.get('avatar')

            if not avatar_data:
                return Response(
                    {"avatar": ["Это поле обязательно."]},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                if current_user.avatar:
                    current_user.avatar.delete()

                format, imgstr = avatar_data.split(';base64,')
                ext = format.split('/')[-1]
                data = ContentFile(
                    base64.b64decode(imgstr),
                    name=f"{uuid.uuid4()}.{ext}")

                current_user.avatar.save(data.name, data, save=True)
                current_user.save()

                avatar_url = request.build_absolute_uri(
                    current_user.avatar.url)

                return Response({"avatar": avatar_url},
                                status=status.HTTP_200_OK)

            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )

        else:
            if current_user.avatar:
                avatar_path = current_user.avatar.path
                if os.path.exists(avatar_path):
                    os.remove(avatar_path)
                current_user.avatar.delete()
                current_user.avatar = None
                current_user.save()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                {"detail": "Аватар отсутствует."},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(
        detail=False,
        permission_classes=[IsAuthenticated],
        serializer_class=UserWithRecipesSerializer,
        pagination_class=SitePagination,
    )
    def subscriptions(self, request):
        """Returns users that current user is subscribed to."""
        subscribed_users = User.objects.filter(
            authors__user=request.user
        ).prefetch_related("recipes")

        paginated_users = self.paginate_queryset(subscribed_users)
        serializer = self.get_serializer(paginated_users, many=True)

        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
        serializer_class=UserWithRecipesSerializer,
    )
    def subscribe(self, request, id=None):
        author = get_object_or_404(User, id=id)
        current_user = request.user

        if request.method == "POST":
            if current_user == author:
                raise ValidationError("Cannot subscribe to yourself")

            subscription, created = Subscription.objects.get_or_create(
                user=current_user, author=author
            )

            if not created:
                raise ValidationError(
                    "You are already subscribed to this user"
                )

            serializer = self.get_serializer(author)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == "DELETE":
            subscription = Subscription.objects.filter(
                user=current_user, author=author
            ).first()

            if not subscription:
                raise ValidationError(
                    {"errors": "Вы не подписаны на этого пользователя"}
                )

            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
