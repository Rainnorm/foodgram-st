# Foodgram

## Описание проекта
«Фудграм» — сайт, на котором пользователи могут публиковать свои рецепты, добавлять чужие рецепты в избранное и подписываться на публикации других авторов.

## Запуск проекта

Создать файл .env в корневой директории проекта, например:


```.env
DB_ENGINE=django.db.backends.postgres 
DB_NAME=postgres                     
POSTGRES_USER=postgres            
POSTGRES_PASSWORD=password          
DB_HOST=db                      
DB_PORT=5432                       
DEBUG=True                    
```

Запустить docker compose:

```bash
docker compose up --build
```

Миграции, сбор статики и загрузка ингредиентов происходит автоматически на этапе сборки билда
```