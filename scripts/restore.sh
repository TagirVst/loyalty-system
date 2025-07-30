#!/bin/bash

# Скрипт для восстановления базы данных из backup
# Использование: ./scripts/restore.sh <backup_file>

set -e

if [ $# -eq 0 ]; then
    echo "❌ Использование: ./scripts/restore.sh <backup_file>"
    echo "📋 Доступные backup'ы:"
    ls -lh backups/*.sql.gz 2>/dev/null || echo "Нет backup'ов"
    exit 1
fi

BACKUP_FILE=$1

# Проверяем существование файла
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Файл backup не найден: $BACKUP_FILE"
    exit 1
fi

# Загружаем переменные окружения
if [ -f ".env" ]; then
    source .env
fi

POSTGRES_DB=${POSTGRES_DB:-loyalty_db}
POSTGRES_USER=${POSTGRES_USER:-loyalty_user}

echo "🔄 Восстановление базы данных из backup: $BACKUP_FILE"

# Проверяем, что контейнер БД запущен
if ! docker-compose ps db | grep -q "Up"; then
    echo "❌ Контейнер базы данных не запущен. Запустите сначала: docker-compose up -d db"
    exit 1
fi

# Предупреждение
echo "⚠️  ВНИМАНИЕ: Это действие полностью заменит текущую базу данных!"
read -p "Продолжить? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Восстановление отменено"
    exit 0
fi

# Создаем backup текущей БД перед восстановлением
echo "💾 Создание backup текущей БД перед восстановлением..."
./scripts/backup.sh "before_restore_$(date +%Y%m%d_%H%M%S)" || echo "⚠️  Не удалось создать backup"

# Восстанавливаем из backup
echo "🗄️  Восстановление базы данных..."

if [[ $BACKUP_FILE == *.gz ]]; then
    # Для сжатых файлов
    zcat $BACKUP_FILE | docker-compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB
else
    # Для несжатых файлов
    cat $BACKUP_FILE | docker-compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB
fi

if [ $? -eq 0 ]; then
    echo "✅ База данных успешно восстановлена из $BACKUP_FILE"
    echo "🔄 Перезапускаем сервисы для применения изменений..."
    docker-compose restart api client_bot barista_bot admin_panel
    echo "🎉 Восстановление завершено!"
else
    echo "❌ Ошибка при восстановлении базы данных"
    exit 1
fi