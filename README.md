# Molecule Search API

Backend-приложение на FastAPI для хранения молекул и субструктурного поиска по SMILES.

## Что реализовано

- CRUD операции для молекул:
  - добавление молекулы
  - получение списка молекул
  - получение молекулы по id
  - обновление молекулы
  - удаление молекулы
- Субструктурный поиск по SMILES с использованием RDKit
- PostgreSQL база данных
- SQLAlchemy ORM
- Docker и Docker Compose
- Swagger UI для проверки API

## Запуск через Docker

В корне проекта выполнить команду:

```bash
docker compose up --build
```

После запуска открыть Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Основные эндпоинты

- `POST /molecules` - добавить молекулу
- `GET /molecules` - получить список молекул
- `GET /molecules/{molecule_id}` - получить молекулу по id
- `PUT /molecules/{molecule_id}` - обновить молекулу
- `DELETE /molecules/{molecule_id}` - удалить молекулу
- `POST /search` - выполнить поиск по переданному списку SMILES
- `POST /search/database` - выполнить поиск по молекулам из базы данных

## Примеры молекул для проверки

```json
{
  "smiles": "CCO",
  "name": "ethanol"
}
```

```json
{
  "smiles": "c1ccccc1",
  "name": "benzene"
}
```

```json
{
  "smiles": "CC(=O)Oc1ccccc1C(=O)O",
  "name": "aspirin"
}
```

## Пример субструктуры для поиска

```text
c1ccccc1
```

Ожидаемый результат: будут найдены молекулы, содержащие бензольное кольцо, например benzene и aspirin.