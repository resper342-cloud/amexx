# American Express Personal Loans & Partner Referral Platform

This workspace contains an American Express (AMEX)-inspired financial-services experience, personal-loan application flow, partner referral portal, and underwriting dashboard. Built with Python's standard library and SQLite, the applicant portal, partner portal, and underwriting operations dashboard are served with zero external framework dependencies.

---

## Key Features & Value Proposition (American Express Personal Loans)

- **Fixed Competitive APR**: Transparent fixed rates from **7.99% to 24.97% APR** with no hidden fees.
- **Zero Origination Fees & Prepayment Penalties**: Borrowers pay $0 in origination fees and can pay off balances early without penalty.
- **Flexible Loan Amounts & Repayment Terms**: Loan options from **$3,500 to $40,000+ USD** across 12, 24, 36, 48, or 60 months.
- **Interactive Loan Amortization Simulator**: Real-time monthly payment calculator computing amortized monthly installments, total interest, and principal schedules.
- **Soft Credit Inquiry**: Pre-qualification checks that do not impact consumer FICO® credit scores.
- **Fast Direct Deposit**: Streamlined disbursements into verified checking accounts in as fast as 1–2 business days.
- **Multi-Step Security & Application Flow**:
  1. **Loan Preferences & Calculator**: Loan amount selection ($3,500 – $40,000) and repayment term (12–60 months).
  2. **Applicant Verification**: Legal identity, contact info, housing status, annual income, and soft inquiry authorization.
  3. **American Express Account Sign-in**: Secure account authentication challenge simulation.
  4. **2-Step Security Verification**: SMS / One-Time Passcode security challenge.
  5. **Loan Approval Dashboard**: Instant approval notification with assigned loan limit, fixed APR, monthly installments, AutoPay setup, and Amex banking disclosures.

---

## Run Locally

```powershell
python server.py
```

- **Applicant Portal**: `http://127.0.0.1:8000/`
- **Admin & Underwriting Operations**: `http://127.0.0.1:8000/admin`
- **Partner & Referral Portal**: `http://127.0.0.1:8000/agent`

The server prints a one-time local admin token at startup (or configure via `AMEX_ADMIN_TOKEN`).

---

## Configuration & Environment Variables

All settings support primary `AMEX_*` environment variables (with backward-compatible fallbacks for prior configurations):

| Variable | Description |
| :--- | :--- |
| `AMEX_ADMIN_TOKEN` | Static secret token for administrative access to `/admin` and underwriting APIs. |
| `AMEX_DB_PATH` | Path to the SQLite database file (defaults to `paypal_credit.sqlite3` or `amex_personal_loans.sqlite3`). |
| `AMEX_TELEGRAM_BOT_TOKEN` | Bot token from `@BotFather` for 24/7 background underwriting alerts. |
| `AMEX_TELEGRAM_CHAT_ID` | Telegram chat ID for administrative alerts on new applications. |
| `AMEX_TELEGRAM_BOT_USERNAME` | Telegram bot username (e.g. `ShackleAmexBot`). |
| `AMEX_SMTP_HOST` | SMTP server host (e.g. `smtp.gmail.com`). |
| `AMEX_SMTP_PORT` | SMTP port (e.g. `587`). |
| `AMEX_SMTP_USERNAME` | SMTP account email address. |
| `AMEX_SMTP_PASSWORD` | SMTP account app password. |
| `AMEX_SIGNING_KEY` | HMAC secret key (at least 32 characters) for tamper-proof referral signatures. |

---

## Telegram Underwriting Alerts

The background supervisor runs 24/7 with auto-reconnect, long polling, and queued outbox delivery:

```powershell
$env:AMEX_TELEGRAM_BOT_TOKEN = "your-bot-token"
$env:AMEX_TELEGRAM_CHAT_ID = "your-admin-chat-id"
python server.py
```

Underwriters receive instant notifications when new American Express Personal Loan applications are submitted, complete with requested loan amount, term, applicant details, referral agent attribution, and verification stage.

---

## Automated Test Suite

Run the full automated test suite (22 comprehensive integration and API tests):

```powershell
python -m unittest -v test_server.py
```
