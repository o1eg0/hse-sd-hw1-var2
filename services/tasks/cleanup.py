from datetime import datetime, timedelta

from sqlmodel import Session, select

from services.shared.db import engine
from services.shared.db_models import CountryRetentionConfigDB, RentalDB


def cleanup_old_orders():
    with Session(engine) as session:
        configs = {
            c.country: c.retention_days
            for c in session.exec(select(CountryRetentionConfigDB)).all()
        }

        rentals = session.exec(select(RentalDB)).all()
        now = datetime.utcnow()

        for r in rentals:
            days = configs.get(r.country, 365)
            if r.finish_time and r.finish_time < now - timedelta(days=days):
                session.delete(r)

        session.commit()


if __name__ == "__main__":
    cleanup_old_orders()
