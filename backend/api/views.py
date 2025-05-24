from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from django.core.files.base import ContentFile
from djoser.views import UserViewSet as DjoserUserViewSet
from django.db.models import Sum
import base64
import uuid
from django.http import HttpResponse

from users.models import User, Subscription
from recipes.models import Recipe, Ingredient, FavoriteRecipe, ShoppingCart
from .serializers import (
    RecipeReadSerializer,
    RecipeWriteSerializer,
    RecipeShortSerializer,
    UserProfileSerializer,
    UserWithRecipesSerializer,
    IngredientSerializer,
    CustomUserCreateSerializer
)
from .filters import IngredientFilter, RecipeFilter
from .permissions import IsAuthorOrReadOnly
from .pagination import SitePagination


class BaseRecipeRelationView:
    """Базовый класс для обработки связей пользователь-рецепт"""
    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated]
    )
    def handle_relation(self, request, pk, relation_model, exists_msg,
                        not_found_msg):
        recipe = get_object_or_404(Recipe, pk=pk)
        user = request.user
        relation = relation_model.objects.filter(user=user, recipe=recipe)

        if request.method == "POST":
            if relation.exists():
                return Response(
                    {"errors": exists_msg},
                    status=status.HTTP_400_BAD_REQUEST
                )
            relation_model.objects.create(user=user, recipe=recipe)
            serializer = RecipeShortSerializer(
                recipe,
                context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == "DELETE":
            if not relation.exists():
                return Response(
                    {"errors": not_found_msg},
                    status=status.HTTP_400_BAD_REQUEST
                )
            relation.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Представление для работы с ингредиентами (только чтение)"""
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filterset_class = IngredientFilter
    filter_backends = [DjangoFilterBackend]
    permission_classes = [AllowAny]
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class RecipeViewSet(viewsets.ModelViewSet, BaseRecipeRelationView):
    """Представление для работы с рецептами"""
    queryset = Recipe.objects.all()
    filter_backends = [DjangoFilterBackend]
    pagination_class = SitePagination
    filterset_class = RecipeFilter
    permission_classes = [IsAuthorOrReadOnly]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return RecipeReadSerializer
        return RecipeWriteSerializer

    def perform_create(self, serializer):
        serializer.save()

    @action(methods=["get"], detail=True, url_path="get-link")
    def get_link_to_recipe(self, request, pk):
        recipe = get_object_or_404(Recipe, pk=pk)
        return Response({
            "short-link": f"{request.get_host()}/s/{recipe.id}"
        })

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        return self.handle_relation(
            request, pk, FavoriteRecipe,
            "Рецепт уже в избранном",
            "Рецепта нет в избранном"
        )

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        return self.handle_relation(
            request, pk, ShoppingCart,
            "Рецепт уже в списке покупок",
            "Рецепта нет в списке покупок"
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        ingredients = (
            ShoppingCart.objects
            .filter(user=request.user)
            .values(
                'recipe__ingredients__name',
                'recipe__ingredients__measurement_unit'
            )
            .annotate(total=Sum('recipe__recipe_ingredients__amount')))
        if not ingredients:
            return Response(
                {"errors": "Список покупок пуст"},
                status=status.HTTP_400_BAD_REQUEST
            )
        content = ["Список покупок:\n"]
        for item in ingredients:
            name = item['recipe__ingredients__name']
            unit = item['recipe__ingredients__measurement_unit']
            amount = item['total']
            content.append(f"- {name} ({unit}): {amount}")

        text_data = "\n".join(content)

        response = HttpResponse(text_data, content_type='text/plain')
        response[
            'Content-Disposition'] = 'attachment; filename="shopping_list.txt"'
        return response


class UserViewSet(DjoserUserViewSet):
    """Представление для работы с пользователями"""
    queryset = User.objects.all().order_by('username')
    pagination_class = SitePagination
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == "create":
            return CustomUserCreateSerializer
        elif self.action in ["me", "retrieve"]:
            return UserProfileSerializer
        elif self.action in ["subscriptions", "subscribe"]:
            return UserWithRecipesSerializer
        return super().get_serializer_class()

    @action(
        methods=["put", "delete"],
        detail=False,
        url_path="me/avatar",
        permission_classes=[IsAuthenticated]
    )
    def avatar(self, request):
        user = request.user
        if request.method == "PUT":
            if 'avatar' not in request.data:
                return Response(
                    {"avatar": ["Это поле обязательно."]},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                avatar_data = request.data['avatar']
                format, imgstr = avatar_data.split(';base64,')
                ext = format.split('/')[-1]

                if user.avatar:
                    user.avatar.delete()

                user.avatar.save(
                    f"{uuid.uuid4()}.{ext}",
                    ContentFile(base64.b64decode(imgstr)),
                    save=True
                )
                return Response(
                    {"avatar": user.avatar.url},
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif request.method == "DELETE":
            if not user.avatar:
                return Response(
                    {"detail": "Аватар отсутствует."},
                    status=status.HTTP_404_NOT_FOUND
                )
            user.avatar.delete()
            user.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated])
    def me(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Требуется авторизация"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        return super().me(request, *args, **kwargs)

    @action(
        detail=False,
        permission_classes=[IsAuthenticated],
        pagination_class=SitePagination
    )
    def subscriptions(self, request):
        subscribed_users = User.objects.filter(
            authors__user=request.user
        ).prefetch_related('recipes')
        page = self.paginate_queryset(subscribed_users)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request, id=None):
        author = get_object_or_404(User, id=id)
        user = request.user
        if request.method == "POST":
            if user == author:
                return Response(
                    {"errors": "Нельзя подписаться на самого себя"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Subscription.objects.filter(user=user, author=author).exists():
                return Response(
                    {"errors": "Вы уже подписаны на этого пользователя"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            Subscription.objects.create(user=user, author=author)
            serializer = self.get_serializer(author)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif request.method == "DELETE":
            subscription = Subscription.objects.filter(
                user=user, author=author
            ).first()
            if not subscription:
                return Response(
                    {"errors": "Вы не подписаны на этого пользователя"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
