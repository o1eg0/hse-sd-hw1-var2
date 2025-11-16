import json
import logging

from fastapi import HTTPException
from httpx import AsyncClient
from redis.asyncio import Redis

from services.shared.model import Config, Tariff
from services.shared.settings import pricing_settings

logger = logging.getLogger(__name__)


async def get_configs_cached(redis: Redis) -> Config:
    """Возвращает конфиг из кеша, если кеш устарел - запрашивает новый"""
    raw = await redis.get(pricing_settings.redis_config_key)
    if raw:
        try:
            return Config(**json.loads(raw))
        except Exception:
            pass

    try:
        async with AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{pricing_settings.base_url}/configs")
            resp.raise_for_status()

        cfg = resp.json()
        await redis.setex(
            pricing_settings.redis_config_key,
            pricing_settings.config_ttl_sec,
            json.dumps(cfg, ensure_ascii=False),
        )
        return Config(**cfg)
    except Exception as e:
        logger.error("Failed to get configs from configs sevice", extra={"error": e})
        return Config(
            price_coeff_settings={"last_banks_increase": 1.5},
            tariff_cache_ttl_sec=pricing_settings.tariff_ttl_sec,
            offer_ttl_sec=pricing_settings.offer_ttl_sec,
            fallback_greedy_coeff=pricing_settings.fallback_greedy_coeff,
        )


async def get_tariff_cached(redis: Redis, tariff_id: str, ttl_sec: int) -> Tariff:
    """Возвращает тариф из кеша, если кеш устарел - запрашивает новый"""
    key = pricing_settings.redis_template_key.format(tariff_id)
    raw = await redis.get(key)
    if raw:
        try:
            return Tariff(**json.loads(raw))
        except Exception:
            pass

    try:
        async with AsyncClient() as client:
            resp = await client.get(
                f"{pricing_settings.base_url}/tariff",
                params={"id": tariff_id},
                timeout=1.0,
            )
            resp.raise_for_status()
            payload = resp.json()

            await redis.setex(key, ttl_sec, json.dumps(payload, ensure_ascii=False))
            return Tariff(**payload)

    except Exception:
        raise HTTPException(503, "Tariff data is stale or upstream unavailable")
