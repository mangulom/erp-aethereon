"""Create the first platform administrator once, explicitly, from the CLI.

Usage: python -m app.bootstrap --email owner@example.com --display-name "Platform owner"
The password is read without echo and never accepted as a command-line argument.
"""
import argparse
from getpass import getpass
from argon2 import PasswordHasher
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import URL

def main() -> None:
    parser = argparse.ArgumentParser(description="Create the initial Aethereon platform administrator.")
    parser.add_argument("--email", required=True, help="Administrator's email address")
    parser.add_argument("--display-name", required=True, help="Administrator's display name")
    args = parser.parse_args()
    password = getpass("New administrator password (minimum 14 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords do not match.")
    if len(password) < 14:
        parser.error("Choose a password with at least 14 characters.")

    database_url = URL.create(
        drivername="postgresql+psycopg2",
        username="aethereon",
        host="localhost",
        port=15432,
        database="aethereon_erp",
        password=getpass("Aethereon database password: "),
    )
    # This setup helper always prompts interactively for the local database credential;
    # the application service continues using its normal DATABASE_URL from .env.
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            count = connection.execute(text("SELECT count(*) FROM users WHERE is_platform_admin = TRUE")).scalar_one()
            if count:
                parser.error("An active platform administrator already exists; refusing to overwrite or add another bootstrap administrator.")
            user_id = connection.execute(
                text("""
                    INSERT INTO users (email, display_name, password_hash, is_platform_admin)
                    VALUES (lower(:email), :name, :password_hash, TRUE)
                    RETURNING id
                """),
                {"email": args.email.strip(), "name": args.display_name.strip(), "password_hash": PasswordHasher(time_cost=3, memory_cost=65_536, parallelism=2).hash(password)},
            ).scalar_one()
            connection.execute(
                text("""
                    INSERT INTO roles (company_id, code, name, description, is_system)
                    VALUES (NULL, 'PLATFORM_ADMIN', 'Platform administrator', 'Platform-wide governance and initial access', TRUE)
                    ON CONFLICT (code) WHERE company_id IS NULL DO NOTHING
                """)
            )
            connection.execute(
                text("""
                    INSERT INTO audit_events (actor_user_id, actor_type, action, entity_type, entity_id)
                    VALUES (:id, 'user', 'identity.bootstrap.admin_created', 'user', :entity_id)
                """),
                {"id": user_id, "entity_id": str(user_id)},
            )
        print(f"Platform administrator created: {args.email.strip().lower()} (ID {user_id})")
    except IntegrityError as exc:
        raise SystemExit("Could not create administrator. The email may already exist; verify the account without resetting its password.") from exc
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
