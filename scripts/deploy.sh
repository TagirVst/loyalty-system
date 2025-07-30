#!/bin/bash

# Скрипт для развертывания системы лояльности
# Использование: ./scripts/deploy.sh [env]
# env: dev (по умолчанию) или prod

set -e

ENV=${1:-dev}
echo "🚀 Развертывание системы лояльности в режиме: $ENV"

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker и попробуйте снова."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Установите Docker Compose и попробуйте снова."
    exit 1
fi

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден. Создаем из .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Файл .env создан. Не забудьте указать токены Telegram ботов!"
    else
        echo "❌ Файл .env.example не найден. Создайте его вручную."
        exit 1
    fi
fi

# Создаем директории для логов
echo "📁 Создание директорий для логов..."
mkdir -p logs/{api,client_bot,barista_bot,admin_panel,postgres}

# Останавливаем старые контейнеры
echo "🛑 Остановка старых контейнеров..."
docker-compose down --remove-orphans

# Создаем backup БД если она существует
if docker volume ls | grep -q loyalty_postgres_data; then
    echo "💾 Создание backup базы данных..."
    ./scripts/backup.sh
fi

# Сборка и запуск контейнеров
echo "🔨 Сборка и запуск контейнеров..."
docker-compose up --build -d

# Ждем запуска БД
echo "⏳ Ожидание запуска базы данных..."
sleep 30

# Проверяем health check БД
echo "🔍 Проверка состояния базы данных..."
timeout=60
elapsed=0
while ! docker-compose exec -T db pg_isready -U ${POSTGRES_USER:-loyalty_user} -d ${POSTGRES_DB:-loyalty_db} > /dev/null 2>&1; do
    if [ $elapsed -ge $timeout ]; then
        echo "❌ Превышено время ожидания запуска БД"
        exit 1
    fi
    echo "Ожидание БД... ($elapsed/$timeout)"
    sleep 5
    elapsed=$((elapsed + 5))
done

# Применяем миграции
echo "🗄️  Применение миграций базы данных..."
docker-compose exec -T api alembic upgrade head

# Загружаем тестовые данные в dev режиме
if [ "$ENV" = "dev" ]; then
    echo "🎭 Загрузка тестовых данных для разработки..."
    docker-compose exec -T api python tests/fixtures.py || echo "⚠️  Тестовые данные не загружены (нормально для первого запуска)"
fi

# Проверяем состояние сервисов
echo "🔍 Проверка состояния сервисов..."
sleep 10

# Функция проверки health check
check_service() {
    local service=$1
    local url=$2
    
    for i in {1..5}; do
        if curl -f -s "$url" > /dev/null; then
            echo "✅ $service работает"
            return 0
        fi
        echo "⏳ Ожидание запуска $service... (попытка $i/5)"
        sleep 10
    done
    echo "❌ $service не отвечает"
    return 1
}

# Проверяем API
if check_service "API" "http://localhost:8000/analytics/summary"; then
    echo "🎉 API готов к работе: http://localhost:8000/docs"
else
    echo "⚠️  API может быть еще не готов. Проверьте логи: docker-compose logs api"
fi

# Проверяем админ-панель  
if check_service "Админ-панель" "http://localhost:8000/"; then
    echo "🎉 Админ-панель готова: http://localhost:8000/"
else
    echo "⚠️  Админ-панель может быть еще не готова. Проверьте логи: docker-compose logs admin_panel"
fi

echo ""
echo "🎉 Развертывание завершено!"
echo ""
echo "📋 Полезные команды:"
echo "  Логи всех сервисов: docker-compose logs -f"
echo "  Логи API: docker-compose logs -f api"
echo "  Логи клиентского бота: docker-compose logs -f client_bot"
echo "  Логи бариста бота: docker-compose logs -f barista_bot"
echo "  Остановка: docker-compose down"
echo "  Backup БД: ./scripts/backup.sh"
echo "  Восстановление БД: ./scripts/restore.sh <backup_file>"
echo ""
echo "🔗 Ссылки:"
echo "  API документация: http://localhost:8000/docs"
echo "  Админ-панель: http://localhost:8000/"
echo "  Swagger API: http://localhost:8000/docs"
echo ""

if [ "$ENV" = "prod" ]; then
    echo "⚠️  ВАЖНО для продакшена:"
    echo "  1. Смените пароли в .env файле"
    echo "  2. Настройте CORS домены в api/main.py"
    echo "  3. Настройте SSL/HTTPS"
    echo "  4. Настройте регулярные backup'ы"
    echo "  5. Настройте мониторинг"
fi