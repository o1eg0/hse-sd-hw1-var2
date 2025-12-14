import logging
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

logger = logging.getLogger(__name__)

DWH_CONN_ID = "dwh_postgres"
DATA_DIR = Path("/opt/airflow/sample_data")
SOURCE_DIR = DATA_DIR / "source"
REFERENCE_DIR = DATA_DIR / "reference"


def create_schemas_and_tables() -> None:
    """Prepare schemas and tables for all DWH layers."""
    hook = PostgresHook(postgres_conn_id=DWH_CONN_ID)
    hook.run(
        """
        CREATE SCHEMA IF NOT EXISTS dwh_raw;
        CREATE SCHEMA IF NOT EXISTS dwh_ods;
        CREATE SCHEMA IF NOT EXISTS dwh_dds;
        CREATE SCHEMA IF NOT EXISTS dwh_marts;

        CREATE TABLE IF NOT EXISTS dwh_raw.offers (
            id text PRIMARY KEY,
            user_id text NOT NULL,
            station_id text NOT NULL,
            tariff_id text NOT NULL,
            country text NOT NULL,
            currency text NOT NULL,
            price_per_hour numeric NOT NULL,
            free_period_min integer NOT NULL,
            deposit numeric NOT NULL,
            pricing_mode text NOT NULL,
            status text NOT NULL,
            expires_at timestamp NOT NULL,
            created_at timestamp NOT NULL,
            updated_at timestamp NOT NULL,
            ingested_at timestamp DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS dwh_raw.rentals (
            id text PRIMARY KEY,
            offer_id text NOT NULL,
            user_id text NOT NULL,
            start_station_id text NOT NULL,
            finish_station_id text,
            country text NOT NULL,
            currency text NOT NULL,
            price_per_hour numeric NOT NULL,
            free_period_min integer NOT NULL,
            deposit numeric NOT NULL,
            total_amount numeric NOT NULL,
            powerbank_id text,
            start_time timestamp NOT NULL,
            finish_time timestamp,
            status text NOT NULL,
            created_at timestamp NOT NULL,
            updated_at timestamp NOT NULL,
            ingested_at timestamp DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS dwh_raw.payments (
            id text PRIMARY KEY,
            order_id text NOT NULL,
            kind text NOT NULL,
            amount numeric NOT NULL,
            currency text NOT NULL,
            status text NOT NULL,
            provider_ref text,
            created_at timestamp NOT NULL,
            updated_at timestamp NOT NULL,
            ingested_at timestamp DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS dwh_raw.users (
            user_id text PRIMARY KEY,
            country text NOT NULL,
            trusted boolean,
            has_subscription boolean,
            ingested_at timestamp DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS dwh_raw.stations (
            station_id text PRIMARY KEY,
            country text NOT NULL,
            city text,
            location text,
            ingested_at timestamp DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS dwh_raw.tariffs (
            tariff_id text PRIMARY KEY,
            country text NOT NULL,
            currency text NOT NULL,
            price_per_hour numeric NOT NULL,
            free_period_min integer NOT NULL,
            default_deposit numeric NOT NULL,
            ingested_at timestamp DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS dwh_ods.offers (
            id text PRIMARY KEY,
            user_id text NOT NULL,
            station_id text NOT NULL,
            tariff_id text NOT NULL,
            country text NOT NULL,
            currency text NOT NULL,
            price_per_hour numeric NOT NULL,
            free_period_min integer NOT NULL,
            deposit numeric NOT NULL,
            pricing_mode text NOT NULL,
            status text NOT NULL,
            expires_at timestamp NOT NULL,
            created_at timestamp NOT NULL,
            updated_at timestamp NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dwh_ods.rentals (
            id text PRIMARY KEY,
            offer_id text NOT NULL,
            user_id text NOT NULL,
            start_station_id text NOT NULL,
            finish_station_id text,
            country text NOT NULL,
            currency text NOT NULL,
            price_per_hour numeric NOT NULL,
            free_period_min integer NOT NULL,
            deposit numeric NOT NULL,
            total_amount numeric NOT NULL,
            powerbank_id text,
            start_time timestamp NOT NULL,
            finish_time timestamp,
            status text NOT NULL,
            created_at timestamp NOT NULL,
            updated_at timestamp NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dwh_ods.payments (
            id text PRIMARY KEY,
            order_id text NOT NULL,
            kind text NOT NULL,
            amount numeric NOT NULL,
            currency text NOT NULL,
            status text NOT NULL,
            provider_ref text,
            created_at timestamp NOT NULL,
            updated_at timestamp NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dwh_ods.users (
            user_id text PRIMARY KEY,
            country text NOT NULL,
            trusted boolean,
            has_subscription boolean
        );

        CREATE TABLE IF NOT EXISTS dwh_ods.stations (
            station_id text PRIMARY KEY,
            country text NOT NULL,
            city text,
            location text
        );

        CREATE TABLE IF NOT EXISTS dwh_ods.tariffs (
            tariff_id text PRIMARY KEY,
            country text NOT NULL,
            currency text NOT NULL,
            price_per_hour numeric NOT NULL,
            free_period_min integer NOT NULL,
            default_deposit numeric NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dwh_dds.dim_date (
            date_key date PRIMARY KEY,
            year integer NOT NULL,
            month integer NOT NULL,
            day integer NOT NULL,
            week integer NOT NULL,
            weekday text NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dwh_dds.dim_station (
            station_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            station_id text UNIQUE NOT NULL,
            country text,
            city text,
            location text
        );

        CREATE TABLE IF NOT EXISTS dwh_dds.dim_tariff (
            tariff_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tariff_id text UNIQUE NOT NULL,
            country text,
            currency text,
            price_per_hour numeric,
            free_period_min integer,
            deposit numeric
        );

        CREATE TABLE IF NOT EXISTS dwh_dds.dim_user (
            user_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id text UNIQUE NOT NULL,
            country text,
            trusted boolean,
            has_subscription boolean
        );

        CREATE TABLE IF NOT EXISTS dwh_dds.fct_rentals (
            rental_id text PRIMARY KEY,
            offer_id text,
            user_key integer REFERENCES dwh_dds.dim_user(user_key),
            start_station_key integer REFERENCES dwh_dds.dim_station(station_key),
            finish_station_key integer REFERENCES dwh_dds.dim_station(station_key),
            tariff_key integer REFERENCES dwh_dds.dim_tariff(tariff_key),
            start_time timestamp,
            finish_time timestamp,
            start_date date,
            finish_date date,
            country text,
            currency text,
            status text,
            pricing_mode text,
            price_per_hour numeric,
            free_period_min integer,
            deposit numeric,
            total_amount numeric,
            duration_min numeric
        );

        CREATE TABLE IF NOT EXISTS dwh_dds.fct_payments (
            payment_id text PRIMARY KEY,
            order_id text,
            payment_kind text,
            status text,
            amount numeric,
            currency text,
            country text,
            payment_created timestamp,
            payment_date date,
            succeeded boolean
        );

        CREATE TABLE IF NOT EXISTS dwh_marts.dashboard_metrics (
            metric_date date,
            country text,
            currency text,
            offers_created integer,
            rentals_started integer,
            rentals_finished integer,
            active_rentals integer,
            revenue_capture numeric,
            payment_success_rate numeric,
            offer_to_rental_conversion numeric,
            fallback_pricing_share numeric,
            avg_duration_min numeric,
            avg_ticket numeric,
            PRIMARY KEY (metric_date, country, currency)
        );
        """,
        autocommit=True,
    )
    logger.info("DWH schemas and tables are ready")


def seed_operational_tables() -> None:
    """
    Load a demo snapshot of operational data into public.* tables
    if they are empty. This simulates microservice replicas.
    """
    hook = PostgresHook(postgres_conn_id=DWH_CONN_ID)
    source_files = [
        (
            "public.offers",
            SOURCE_DIR / "offers.csv",
            "id,user_id,station_id,tariff_id,country,currency,price_per_hour,free_period_min,deposit,pricing_mode,status,expires_at,created_at,updated_at",
        ),
        (
            "public.rentals",
            SOURCE_DIR / "rentals.csv",
            "id,offer_id,user_id,start_station_id,finish_station_id,country,currency,price_per_hour,free_period_min,deposit,total_amount,powerbank_id,start_time,finish_time,status,created_at,updated_at",
        ),
        (
            "public.payments",
            SOURCE_DIR / "payments.csv",
            "id,order_id,kind,amount,currency,status,provider_ref,created_at,updated_at",
        ),
    ]

    with hook.get_conn() as conn, conn.cursor() as cur:
        for table, path, columns in source_files:
            cur.execute("SELECT to_regclass(%s)", (table,))
            if cur.fetchone()[0] is None:
                raise RuntimeError(
                    f"{table} is missing. Run alembic migrations (e.g. rental-api container) before the ETL."
                )

            cur.execute(f"SELECT count(*) FROM {table}")
            rows = cur.fetchone()[0]
            if rows and rows > 0:
                logger.info("Skip seeding %s: table already has %s rows", table, rows)
                continue
            if not path.exists():
                raise FileNotFoundError(path)

            logger.info("Loading %s from %s", table, path)
            with open(path, "r", encoding="utf-8") as fh:
                cur.copy_expert(
                    f"COPY {table} ({columns}) FROM STDIN WITH CSV HEADER NULL ''",
                    fh,
                )
        conn.commit()


def load_reference_raw() -> None:
    """Load slowly changing reference data (users/stations/tariffs) into raw layer."""
    hook = PostgresHook(postgres_conn_id=DWH_CONN_ID)
    files = [
        ("dwh_raw.users", REFERENCE_DIR / "users.csv", "user_id,country,trusted,has_subscription"),
        ("dwh_raw.stations", REFERENCE_DIR / "stations.csv", "station_id,country,city,location"),
        (
            "dwh_raw.tariffs",
            REFERENCE_DIR / "tariffs.csv",
            "tariff_id,country,currency,price_per_hour,free_period_min,default_deposit",
        ),
    ]
    with hook.get_conn() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE dwh_raw.users, dwh_raw.stations, dwh_raw.tariffs")
        for table, path, columns in files:
            if not path.exists():
                raise FileNotFoundError(path)
            logger.info("Refreshing %s from %s", table, path)
            with open(path, "r", encoding="utf-8") as fh:
                cur.copy_expert(
                    f"COPY {table} ({columns}) FROM STDIN WITH CSV HEADER NULL ''",
                    fh,
                )
        conn.commit()


def snapshot_operational_raw() -> None:
    """Copy operational tables into raw layer with ingestion timestamp."""
    hook = PostgresHook(postgres_conn_id=DWH_CONN_ID)
    hook.run(
        """
        TRUNCATE dwh_raw.offers, dwh_raw.rentals, dwh_raw.payments;

        INSERT INTO dwh_raw.offers (
            id, user_id, station_id, tariff_id, country, currency,
            price_per_hour, free_period_min, deposit, pricing_mode, status,
            expires_at, created_at, updated_at, ingested_at
        )
        SELECT
            id, user_id, station_id, tariff_id, country, currency,
            price_per_hour, free_period_min, deposit, pricing_mode, status,
            expires_at, created_at, updated_at, now()
        FROM public.offers;

        INSERT INTO dwh_raw.rentals (
            id, offer_id, user_id, start_station_id, finish_station_id, country,
            currency, price_per_hour, free_period_min, deposit, total_amount,
            powerbank_id, start_time, finish_time, status, created_at, updated_at, ingested_at
        )
        SELECT
            id, offer_id, user_id, start_station_id, finish_station_id, country,
            currency, price_per_hour, free_period_min, deposit, total_amount,
            powerbank_id, start_time, finish_time, status, created_at, updated_at, now()
        FROM public.rentals;

        INSERT INTO dwh_raw.payments (
            id, order_id, kind, amount, currency, status, provider_ref,
            created_at, updated_at, ingested_at
        )
        SELECT
            id, order_id, kind, amount, currency, status, provider_ref,
            created_at, updated_at, now()
        FROM public.payments;
        """,
        autocommit=True,
    )
    logger.info("Snapshots loaded into dwh_raw.*")


def build_ods_layer() -> None:
    """Normalize raw data into ODS layer."""
    hook = PostgresHook(postgres_conn_id=DWH_CONN_ID)
    hook.run(
        """
        TRUNCATE dwh_ods.offers, dwh_ods.rentals, dwh_ods.payments,
                 dwh_ods.users, dwh_ods.stations, dwh_ods.tariffs;

        INSERT INTO dwh_ods.offers (
            id, user_id, station_id, tariff_id, country, currency,
            price_per_hour, free_period_min, deposit, pricing_mode, status,
            expires_at, created_at, updated_at
        )
        SELECT
            id, user_id, station_id, tariff_id, country, currency,
            price_per_hour, free_period_min, deposit, pricing_mode, status,
            expires_at, created_at, updated_at
        FROM dwh_raw.offers;

        INSERT INTO dwh_ods.rentals (
            id, offer_id, user_id, start_station_id, finish_station_id, country,
            currency, price_per_hour, free_period_min, deposit, total_amount,
            powerbank_id, start_time, finish_time, status, created_at, updated_at
        )
        SELECT
            id, offer_id, user_id, start_station_id, finish_station_id, country,
            currency, price_per_hour, free_period_min, deposit, total_amount,
            powerbank_id, start_time, finish_time, status, created_at, updated_at
        FROM dwh_raw.rentals;

        INSERT INTO dwh_ods.payments (
            id, order_id, kind, amount, currency, status, provider_ref,
            created_at, updated_at
        )
        SELECT
            id, order_id, kind, amount, currency, status, provider_ref,
            created_at, updated_at
        FROM dwh_raw.payments;

        INSERT INTO dwh_ods.users (user_id, country, trusted, has_subscription)
        SELECT user_id, country, trusted, has_subscription FROM dwh_raw.users;

        INSERT INTO dwh_ods.stations (station_id, country, city, location)
        SELECT station_id, country, city, location FROM dwh_raw.stations;

        INSERT INTO dwh_ods.tariffs (tariff_id, country, currency, price_per_hour, free_period_min, default_deposit)
        SELECT tariff_id, country, currency, price_per_hour, free_period_min, default_deposit
        FROM dwh_raw.tariffs;
        """,
        autocommit=True,
    )
    logger.info("ODS layer refreshed")


def build_dds_layer() -> None:
    """Build dimensions and fact tables."""
    hook = PostgresHook(postgres_conn_id=DWH_CONN_ID)
    hook.run(
        """
        INSERT INTO dwh_dds.dim_station (station_id, country, city, location)
        SELECT station_id, country, city, location FROM dwh_ods.stations
        ON CONFLICT (station_id) DO UPDATE
        SET country = EXCLUDED.country,
            city = EXCLUDED.city,
            location = EXCLUDED.location;

        INSERT INTO dwh_dds.dim_tariff (tariff_id, country, currency, price_per_hour, free_period_min, deposit)
        SELECT tariff_id, country, currency, price_per_hour, free_period_min, default_deposit
        FROM dwh_ods.tariffs
        ON CONFLICT (tariff_id) DO UPDATE
        SET country = EXCLUDED.country,
            currency = EXCLUDED.currency,
            price_per_hour = EXCLUDED.price_per_hour,
            free_period_min = EXCLUDED.free_period_min,
            deposit = EXCLUDED.deposit;

        INSERT INTO dwh_dds.dim_user (user_id, country, trusted, has_subscription)
        SELECT user_id, country, trusted, has_subscription FROM dwh_ods.users
        ON CONFLICT (user_id) DO UPDATE
        SET country = EXCLUDED.country,
            trusted = EXCLUDED.trusted,
            has_subscription = EXCLUDED.has_subscription;

        WITH bounds AS (
            SELECT
                COALESCE(MIN(d)::date, CURRENT_DATE) AS min_date,
                COALESCE(MAX(d)::date, CURRENT_DATE) AS max_date
            FROM (
                SELECT created_at AS d FROM dwh_ods.offers
                UNION ALL
                SELECT start_time FROM dwh_ods.rentals
                UNION ALL
                SELECT created_at FROM dwh_ods.payments
            ) t
        )
        INSERT INTO dwh_dds.dim_date (date_key, year, month, day, week, weekday)
        SELECT
            gs::date AS date_key,
            EXTRACT(YEAR FROM gs)::int AS year,
            EXTRACT(MONTH FROM gs)::int AS month,
            EXTRACT(DAY FROM gs)::int AS day,
            EXTRACT(WEEK FROM gs)::int AS week,
            TO_CHAR(gs, 'Dy') AS weekday
        FROM bounds, generate_series(bounds.min_date, bounds.max_date, interval '1 day') gs
        ON CONFLICT (date_key) DO NOTHING;

        TRUNCATE dwh_dds.fct_rentals;
        INSERT INTO dwh_dds.fct_rentals (
            rental_id, offer_id, user_key, start_station_key, finish_station_key, tariff_key,
            start_time, finish_time, start_date, finish_date, country, currency, status,
            pricing_mode, price_per_hour, free_period_min, deposit, total_amount, duration_min
        )
        SELECT
            r.id,
            r.offer_id,
            u.user_key,
            ss.station_key,
            fs.station_key,
            t.tariff_key,
            r.start_time,
            r.finish_time,
            r.start_time::date,
            r.finish_time::date,
            r.country,
            r.currency,
            r.status,
            o.pricing_mode,
            r.price_per_hour,
            r.free_period_min,
            r.deposit,
            r.total_amount,
            CASE
                WHEN r.finish_time IS NOT NULL THEN EXTRACT(EPOCH FROM (r.finish_time - r.start_time)) / 60.0
                ELSE NULL
            END AS duration_min
        FROM dwh_ods.rentals r
        LEFT JOIN dwh_ods.offers o ON o.id = r.offer_id
        LEFT JOIN dwh_dds.dim_user u ON u.user_id = r.user_id
        LEFT JOIN dwh_dds.dim_station ss ON ss.station_id = r.start_station_id
        LEFT JOIN dwh_dds.dim_station fs ON fs.station_id = r.finish_station_id
        LEFT JOIN dwh_dds.dim_tariff t ON t.tariff_id = o.tariff_id;

        TRUNCATE dwh_dds.fct_payments;
        INSERT INTO dwh_dds.fct_payments (
            payment_id, order_id, payment_kind, status, amount, currency,
            country, payment_created, payment_date, succeeded
        )
        SELECT
            p.id,
            p.order_id,
            p.kind,
            p.status,
            p.amount,
            p.currency,
            COALESCE(r.country, o.country) AS country,
            p.created_at,
            p.created_at::date,
            p.status = 'SUCCEEDED'
        FROM dwh_ods.payments p
        LEFT JOIN dwh_ods.rentals r ON r.id = p.order_id
        LEFT JOIN dwh_ods.offers o ON o.id = r.offer_id;
        """,
        autocommit=True,
    )
    logger.info("DDS layer built")


def build_marts_layer() -> None:
    """Aggregate facts into dashboard mart."""
    hook = PostgresHook(postgres_conn_id=DWH_CONN_ID)
    hook.run(
        """
        TRUNCATE dwh_marts.dashboard_metrics;

        WITH offer_metrics AS (
            SELECT created_at::date AS metric_date, country, currency, count(*) AS offers_created
            FROM dwh_ods.offers
            GROUP BY 1, 2, 3
        ),
        rental_start AS (
            SELECT
                start_time::date AS metric_date,
                country,
                currency,
                count(*) AS rentals_started,
                count(*) FILTER (WHERE status = 'ACTIVE') AS active_rentals,
                count(*) FILTER (WHERE pricing_mode = 'FALLBACK_GREEDY') AS fallback_rentals
            FROM dwh_dds.fct_rentals
            GROUP BY 1, 2, 3
        ),
        rental_finish AS (
            SELECT
                finish_time::date AS metric_date,
                country,
                currency,
                count(*) AS rentals_finished,
                avg(duration_min) AS avg_duration_min,
                avg(total_amount) AS avg_ticket
            FROM dwh_dds.fct_rentals
            WHERE finish_time IS NOT NULL
            GROUP BY 1, 2, 3
        ),
        payment_metrics AS (
            SELECT
                payment_date AS metric_date,
                country,
                currency,
                count(*) AS payments_total,
                count(*) FILTER (WHERE status = 'SUCCEEDED') AS payments_succeeded,
                sum(amount) FILTER (WHERE payment_kind = 'CAPTURE' AND status = 'SUCCEEDED') AS revenue_capture
            FROM dwh_dds.fct_payments
            GROUP BY 1, 2, 3
        ),
        all_dates AS (
            SELECT DISTINCT metric_date FROM (
                SELECT metric_date FROM offer_metrics
                UNION SELECT metric_date FROM rental_start
                UNION SELECT metric_date FROM rental_finish
                UNION SELECT metric_date FROM payment_metrics
            ) t
        ),
        countries AS (
            SELECT DISTINCT country, currency FROM (
                SELECT country, currency FROM dwh_dds.fct_rentals
                UNION
                SELECT country, currency FROM dwh_ods.offers
            ) t
        ),
        grid AS (
            SELECT ad.metric_date, c.country, c.currency
            FROM all_dates ad
            CROSS JOIN countries c
        )
        INSERT INTO dwh_marts.dashboard_metrics (
            metric_date, country, currency, offers_created, rentals_started, rentals_finished,
            active_rentals, revenue_capture, payment_success_rate, offer_to_rental_conversion,
            fallback_pricing_share, avg_duration_min, avg_ticket
        )
        SELECT
            g.metric_date,
            g.country,
            g.currency,
            COALESCE(o.offers_created, 0) AS offers_created,
            COALESCE(rs.rentals_started, 0) AS rentals_started,
            COALESCE(rf.rentals_finished, 0) AS rentals_finished,
            COALESCE(rs.active_rentals, 0) AS active_rentals,
            COALESCE(pm.revenue_capture, 0) AS revenue_capture,
            ROUND(COALESCE(pm.payments_succeeded::numeric / NULLIF(pm.payments_total, 0), 0), 4) AS payment_success_rate,
            ROUND(COALESCE(rs.rentals_started::numeric / NULLIF(o.offers_created, 0), 0), 4) AS offer_to_rental_conversion,
            ROUND(COALESCE(rs.fallback_rentals::numeric / NULLIF(rs.rentals_started, 0), 0), 4) AS fallback_pricing_share,
            ROUND(COALESCE(rf.avg_duration_min, 0), 2) AS avg_duration_min,
            ROUND(COALESCE(rf.avg_ticket, 0), 2) AS avg_ticket
        FROM grid g
        LEFT JOIN offer_metrics o ON o.metric_date = g.metric_date AND o.country = g.country AND o.currency = g.currency
        LEFT JOIN rental_start rs ON rs.metric_date = g.metric_date AND rs.country = g.country AND rs.currency = g.currency
        LEFT JOIN rental_finish rf ON rf.metric_date = g.metric_date AND rf.country = g.country AND rf.currency = g.currency
        LEFT JOIN payment_metrics pm ON pm.metric_date = g.metric_date AND pm.country = g.country AND pm.currency = g.currency
        WHERE COALESCE(o.offers_created, rs.rentals_started, rf.rentals_finished, pm.payments_total) IS NOT NULL;
        """,
        autocommit=True,
    )
    logger.info("Mart dwh_marts.dashboard_metrics refreshed")


default_args = {
    "owner": "dwh",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="dwh_business_etl",
    default_args=default_args,
    start_date=datetime(2024, 12, 1),
    schedule_interval="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["dwh", "powerbank"],
) as dag:
    dag.doc_md = """
    ### DWH ETL
    1. Поднимает схемы и таблицы `raw/ods/dds/marts`.
    2. Подливает демо-снэпшот публичных таблиц (имитация микросервисов).
    3. Перекладывает данные по слоям до витрины `dwh_marts.dashboard_metrics`,
       которая используется в Grafana.
    """

    create_tables = PythonOperator(
        task_id="create_schemas_and_tables", python_callable=create_schemas_and_tables
    )
    seed_source = PythonOperator(task_id="seed_operational_tables", python_callable=seed_operational_tables)
    load_reference = PythonOperator(task_id="load_reference_raw", python_callable=load_reference_raw)
    snapshot_raw = PythonOperator(task_id="snapshot_operational_raw", python_callable=snapshot_operational_raw)
    build_ods = PythonOperator(task_id="build_ods_layer", python_callable=build_ods_layer)
    build_dds = PythonOperator(task_id="build_dds_layer", python_callable=build_dds_layer)
    build_marts = PythonOperator(task_id="build_marts_layer", python_callable=build_marts_layer)

    create_tables >> seed_source >> load_reference >> snapshot_raw >> build_ods >> build_dds >> build_marts
