import logging
import logging.handlers
import os
from pathlib import Path

def setup_logging(service_name: str, log_level: str = "INFO"):
    """Настройка логирования для сервиса"""
    
    # Создаем директорию для логов если не существует
    log_dir = Path("logs") / service_name
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Настройка форматтера
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Основной логгер
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие handlers
    logger.handlers.clear()
    
    # Console handler для отладки
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler для основных логов
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / f"{service_name}.log",
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Error handler для ошибок
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / f"{service_name}_errors.log",
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    return logger

def setup_api_logging():
    """Настройка логирования для API"""
    return setup_logging("api")

def setup_bot_logging(bot_type: str):
    """Настройка логирования для ботов"""
    return setup_logging(f"{bot_type}_bot")

def setup_admin_logging():
    """Настройка логирования для админ-панели"""
    return setup_logging("admin_panel")