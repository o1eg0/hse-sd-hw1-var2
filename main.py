import time
import uuid
from datetime import datetime

import data_requests as dr
from model import OfferData, OrderData

# amazingly fast and totally inreliable databases
offers_database = {}
orders_database = {}
order_index_pb = {}

MAGIC_CONSTANT = 2


def handle_create_offer_request(station_id: str, user_id: str):
    # quite a sequential execution of requests, could be improved!
    station_data = dr.get_station_data(station_id)

    tariff = dr.get_tariff(station_data.tariff_id)

    user_profile = dr.get_user_profile(user_id)

    configs = dr.get_configs()

    # all fetching is done, finally....
    # start building actual response

    # adjust with configuration settings
    actual_price_per_hour = tariff.price_per_hour
    if configs.price_coeff_settings is not None:
        available_powerbanks = sum(
            0 if slot.empty else 1 for slot in station_data.slots
        )
        if available_powerbanks <= MAGIC_CONSTANT:
            increase = float(configs.price_coeff_settings["last_banks_increase"])
            actual_price_per_hour = int(actual_price_per_hour * increase)
        print(f">> Available powerbanks: {available_powerbanks}")

    actual_free_period_min = tariff.free_period_min
    if user_profile.has_subscribtion:
        actual_free_period = max(actual_free_period_min, 30)
        print(actual_free_period)

    offer = OfferData(
        str(uuid.uuid4()),
        user_id=user_id,
        station_id=station_id,
        price_per_hour=actual_price_per_hour,
        free_period_min=actual_free_period_min,
        deposit=0 if user_profile.trusted else tariff.default_deposit,
    )

    print(f">> New offer! {offer}")

    # save it immediately
    offers_database[offer.id] = offer
    return offer


def handle_start_order_request(offer_id: str):
    offer = offers_database.pop(offer_id)
    # race condition is possible here!

    order = OrderData(
        str(uuid.uuid4()),
        user_id=offer.user_id,
        start_station_id=offer.station_id,
        finish_station_id=None,
        price_per_hour=offer.price_per_hour,
        free_period_min=offer.free_period_min,
        deposit=offer.deposit,
        total_amount=0,
        start_time=datetime.now(),
        finish_time=None,
    )
    # money is very important thing!
    dr.hold_money_for_order(offer.user_id, order.id, offer.deposit)
    # Eject powerbank
    order.powerbank_id = dr.eject_powerbank(offer.station_id).powerbank_id

    if not order.powerbank_id:
        print(f">> No powerbank available at station {offer.station_id}")
        dr.clear_money_for_order(order.user_id, order.id, 0)

        return None

    print(f">> Order was started! powerbank_id={order.powerbank_id}")

    orders_database[order.id] = order
    order_index_pb[order.powerbank_id] = order.id
    return order


def handle_return_powerbank_request(powerbank_id: str, station_id: str):
    order_id = order_index_pb.pop(powerbank_id)
    order = orders_database[order_id]

    order.finish_station_id = station_id
    order.finish_time = datetime.now()
    duration = order.finish_time - order.start_time
    if duration.total_seconds() < order.free_period_min * 60:
        order.total_amount = 0
    else:
        order.total_amount = int(duration.total_hours()) * order.price_per_hour
    dr.clear_money_for_order(order.user_id, order_id, order.total_amount)
    print(f">> Order was finished! Total amount: {order.total_amount}")


if __name__ == "__main__":
    print("> Starting first scenario! <")
    offer1 = handle_create_offer_request("some-station-id", "some-user-id")
    order1 = handle_start_order_request(offer1.id)

    time.sleep(1)
    handle_return_powerbank_request(order1.powerbank_id, "another-station-id")
    print("< First scenario is over!\n\n")

    print("> Starting second scenario! <")
    offer2 = handle_create_offer_request("empty-station-id", "some-user-id")
    order2 = handle_start_order_request(offer2.id)
    print("< Second scenario is over!\n\n")
