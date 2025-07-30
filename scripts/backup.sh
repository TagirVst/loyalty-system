#!/bin/bash

# Скрипт для создания backup базы данных
# Использование: ./scripts/backup.sh [backup_name]

set -e

# Загружаем переменные окружения
if [ -f ".env" ]; then
    source .env
fi

POSTGRES_DB=${POSTGRES_DB:-loyalty_db}
POSTGRES_USER=${POSTGRES_USER:-loyalty_user}
BACKUP_NAME=${1:-"backup_$(date +%Y%m%d_%H%M%S)"}
BACKUP_DIR="backups"
BACKUP_FILE="$BACKUP_DIR/${BACKUP_NAME}.sql"

echo "💾 Создание backup базы данных..."

# Создаем директорию для backup'ов
mkdir -p $BACKUP_DIR

# Проверяем, что контейнер БД запущен
if ! docker-compose ps db | grep -q "Up"; then
    echo "❌ Контейнер базы данных не запущен"
    exit 1
fi

# Создаем backup
echo "🗄️  Экспорт базы данных $POSTGRES_DB..."
docker-compose exec -T db pg_dump -U $POSTGRES_USER -d $POSTGRES_DB --clean --if-exists > $BACKUP_FILE

if [ $? -eq 0 ]; then
    # Сжимаем backup
    echo "🗜️  Сжатие backup..."
    gzip $BACKUP_FILE
    BACKUP_FILE="${BACKUP_FILE}.gz"
    
    # Проверяем размер файла
    SIZE=$(du -h $BACKUP_FILE | cut -f1)
    
    echo "✅ Backup успешно создан: $BACKUP_FILE (размер: $SIZE)"
    
    # Удаляем старые backup'ы (старше 30 дней)
    echo "🧹 Очистка старых backup'ов..."
    find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
    
    echo "📋 Доступные backup'ы:"
    ls -lh $BACKUP_DIR/*.sql.gz 2>/dev/null || echo "Нет backup'ов"
    
else
    echo "❌ Ошибка при создании backup"
    rm -f $BACKUP_FILE
    exit 1
fi