import requests

from model import Tariff, UserProfile, Slot, StationData, ConfigMap, EjectResponse

station_http = 'http://localhost:3629/station-data'
tariff_http = 'http://localhost:3629/tariff'
user_http = 'http://localhost:3629/user-profile'
config_http = 'http://localhost:3629/configs'
eject_powerbank_http = 'http://localhost:3629/eject-powerbank'
hold_money_http = 'http://localhost:3629/hold-money-for-order'
clear_money_http = 'http://localhost:3629/clear-money-for-order'


def get_station_data(station_id: str) -> StationData:
    raw_data = requests.get(station_http, params={'id': station_id})

    # TODO: error handling

    slots = [Slot(index=slot['index'], empty=slot['empty'], charge=slot['charge']) for slot in raw_data.json()['slots']]
    return StationData(id=station_id, tariff_id=raw_data.json()['tariff_id'],
                       location=raw_data.json()['location'],
                       slots=slots)


def get_tariff(zone_id: str) -> Tariff:
    raw_data = requests.get(tariff_http, params={'id': zone_id})

    # TODO: error handling

    return Tariff(id=zone_id,
                  price_per_hour=int(raw_data.json()['price_per_hour']),
                  free_period_min=int(raw_data.json()['free_period_min']),
                  default_deposit=int(raw_data.json()['default_deposit']))


def get_user_profile(user_id: str) -> UserProfile:
    raw_data = requests.get(user_http, params={'id': user_id})

    # TODO: error handling

    return UserProfile(id=user_id, has_subscribtion=bool(raw_data.json()['has_subscribtion']),
                       trusted=bool(raw_data.json()['trusted']))


def get_configs() -> ConfigMap:
    raw_data = requests.get(config_http)

    # TODO: error handling

    return ConfigMap(raw_data.json())


def eject_powerbank(station_id: str) -> EjectResponse:
    raw_data = requests.get(eject_powerbank_http, params={'station_id': station_id})

    # TODO: error handling

    return EjectResponse(success=raw_data.json()['success'],
                         powerbank_id=raw_data.json()['powerbank_id'])


def hold_money_for_order(user_id: str, order_id: str, amount: int):
    requests.post(hold_money_http,
                  json={'user_id': user_id, 'order_id': order_id, 'amount': amount})
    # TODO: error handling


def clear_money_for_order(user_id: str, order_id: str, amount: int):
    requests.post(clear_money_http,
                  json={'user_id': user_id, 'order_id': order_id, 'amount': amount})
    # TODO: error handling
