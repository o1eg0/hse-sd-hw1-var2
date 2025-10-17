# Доменные сущности

- Пользователь (User): id, сегмент/тарифная категория, страна по умолчанию.

- Станция (Station): id, страна, геолокация, статус, доступный инвентарь.

- Пауэрбанк (Powerbank): id, текущая станция/в аренде, статус.

- Тариф (Tariff): id, страна, валюта, прайсинг-правила (помесячно/поминутно, депозит, пени), версия.

- Оффер (Offer): id, user_id, station_id, snapshot тарифа, валюта, страна, expires_at, версия/хэш.

- Заказ (Order): id, user_id, station_id, powerbank_id, offer_id, snapshot тарифа, страна, валюта, started_at, ended_at, статус (created/active/returned/closed), накопленная стоимость, состояние платежа.

- Платеж (Payment/Transaction): id, rental_id, тип (authorize/capture/refund), сумма, валюта, состояние, reference провайдера.

- Политика хранения (RetentionPolicy): страна, срок хранения (дней), дата последней смены.

- Конфигурация (Config): ключ, значение, версия, ttl, источник.
