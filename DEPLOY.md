# Деплой: systemd + nginx

Инструкция для Ubuntu/Debian. API будет доступно через nginx по домену.

## 1. Подготовка сервера

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv nginx
```

## 2. Установка приложения

```bash
sudo mkdir -p /opt/yookassa-to-mynalog
sudo chown $USER:$USER /opt/yookassa-to-mynalog

cd /opt/yookassa-to-mynalog
git clone https://github.com/grandvan709/yookassa-to-mynalog.git .
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Конфигурация

```bash
cp .env.example .env
nano .env
```

Заполнить обязательные переменные. Для продакшена рекомендуется явно указать путь к базе:

```env
MOY_NALOG_LOGIN='your_inn'
MOY_NALOG_PASSWORD='your_password'
DB_PATH='/opt/yookassa-to-mynalog/checks.db'
API_TOKEN='сгенерируйте_надёжный_токен'
```

Сгенерировать токен:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 4. Проверка запуска

```bash
cd /opt/yookassa-to-mynalog/app
/opt/yookassa-to-mynalog/.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Проверить: `curl http://127.0.0.1:8000/docs` — должна вернуться HTML-страница Swagger.

Остановить (Ctrl+C) и перейти к настройке systemd.

## 5. systemd-сервис

```bash
sudo nano /etc/systemd/system/yookassa-nalog.service
```

Содержимое:

```ini
[Unit]
Description=YooKassa to MyNalog API
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/yookassa-to-mynalog/app
ExecStart=/opt/yookassa-to-mynalog/.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

EnvironmentFile=/opt/yookassa-to-mynalog/.env

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/yookassa-to-mynalog

[Install]
WantedBy=multi-user.target
```

Права на директорию:

```bash
sudo chown -R www-data:www-data /opt/yookassa-to-mynalog
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable yookassa-nalog
sudo systemctl start yookassa-nalog
sudo systemctl status yookassa-nalog
```

Логи:

```bash
sudo journalctl -u yookassa-nalog -f
```

## 6. nginx

```bash
sudo nano /etc/nginx/sites-available/yookassa-nalog
```

Содержимое (заменить `your-domain.ru` на свой домен):

```nginx
server {
    listen 80;
    server_name your-domain.ru;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Активировать:

```bash
sudo ln -s /etc/nginx/sites-available/yookassa-nalog /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 7. HTTPS (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.ru
```

Certbot автоматически обновит конфиг nginx и настроит автопродление сертификата.

## 8. Проверка

```bash
# Создать чек
curl -X POST https://your-domain.ru/checks \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"payment_id": "test-123", "amount": 100.00, "description": "Тестовый чек"}'

# Аннулировать чек
curl -X POST https://your-domain.ru/checks/test-123/cancel \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Обновление

```bash
cd /opt/yookassa-to-mynalog
sudo -u www-data git pull
sudo -u www-data .venv/bin/pip install -r requirements.txt
sudo systemctl restart yookassa-nalog
```

## Полезные команды

```bash
sudo systemctl status yookassa-nalog    # статус
sudo systemctl restart yookassa-nalog   # перезапуск
sudo journalctl -u yookassa-nalog -f    # логи в реальном времени
sudo journalctl -u yookassa-nalog --since "1 hour ago"  # логи за последний час
```
