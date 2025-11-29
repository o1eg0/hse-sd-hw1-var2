import uuid
import random
import logging

from locust import HttpUser, task, between, SequentialTaskSet

RENTAL_API_HOST = "http://rental-api:8080"

class RealUserScenario(SequentialTaskSet):
    """
    Полный цикл одной аренды.
    Гарантирует порядок выполнения: Create Offer -> Start Rental -> Finish Rental.
    """

    def on_start(self):
        self.user_id = str(uuid.uuid4())

        self.station = random.choice(["ru-station-1", "ru-station-2"])
        self.tariff_id = "1"
        
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        self.offer_id = None
        self.rental_id = None

    @task
    def step_1_create_offer(self):
        """
        1. Идем в RENTAL-API, чтобы рассчитать стоимость и сохранить оффер в Redis.
        POST http://rental-api:8080/v1/offers
        """
        payload = {
            "user_id": self.user_id,
            "station_id": self.station,
            "tariff_id": self.tariff_id,
        }

        with self.client.post(
            f"{RENTAL_API_HOST}/v1/offers",
            json=payload,
            headers=self.headers,
            name="1. Create Offer (Pricing)",
            catch_response=True
        ) as response:
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                self.offer_id = data.get("offer_id")
            else:
                response.failure(f"Offer failed: {response.status_code} {response.text}")
                self.interrupt()

    @task
    def step_2_start_rental(self):
        """
        2. Идем в RENTAL-API, чтобы начать аренду (используя offer_id).
        Это создаст запись в Postgres.
        POST http://rental-api:8080/v1/rentals
        """
        if not self.offer_id:
            return

        idem_key = str(uuid.uuid4())
        current_headers = self.headers.copy()
        current_headers["Idempotency-Key"] = idem_key

        payload = {
            "offer_id": self.offer_id
        }

        with self.client.post(
            f"{RENTAL_API_HOST}/v1/rentals",
            json=payload,
            headers=current_headers,
            name="2. Start Rental (Rental API)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.rental_id = data.get("rental_id")
            else:
                if response.status_code == 409:
                    response.success() 
                    self.interrupt()
                else:
                    response.failure(f"Rental Start failed: {response.status_code} {response.text}")
                    self.interrupt()

    @task
    def step_3_simulate_usage(self):
        """
        3. Имитация реального использования (пауза).
        Locust тут просто ждет time.sleep, который задан в wait_time User-класса
        """
        pass

    @task
    def step_4_finish_rental(self):
        """
        4. Завершаем аренду. Сервис обновит запись в Postgres и начислит долг.
        POST http://rental-api:8080/v1/rentals/{id}/finish
        """
        if not self.rental_id:
            return
        
        idem_key = str(uuid.uuid4())
        current_headers = self.headers.copy()
        current_headers["Idempotency-Key"] = idem_key

        url = f"{RENTAL_API_HOST}/v1/rentals/{self.rental_id}/return"
        
        with self.client.post(
            url,
            headers=current_headers,
            name="3. Finish Rental (Rental API)",
            catch_response=True
        ) as response:
            if response.status_code not in [200, 204]:
                response.failure(f"Finish failed: {response.status_code}")


class ProductionLoadUser(HttpUser):
    tasks = [RealUserScenario]
    wait_time = between(2, 5)
