# Live Vultr Smoke Test

This verifies real Vultr Serverless Inference without committing secrets.

PowerShell setup:

```powershell
cd backend
Copy-Item .env.example .env
notepad .env
```

Add your key only in `backend/.env` (never commit it):

```dotenv
VULTR_API_KEY=
VULTR_INFERENCE_URL=https://api.vultrinference.com/v1
VULTR_MODEL=
TOSCO_FALLBACK=true
TOSCO_USE_SYSTEM_TRUST_STORE=true
VULTR_CA_BUNDLE=
```

Then run:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python scripts\vultr_live_smoke.py
```

If the live call still fails because the adapter cannot parse Vultr's response shape, run:

```powershell
python scripts\vultr_live_smoke.py --show-response-shape
```

Expected:
- PASS Level 1
- PASS Level 2
- PASS Level 3
- LIVE VULTR SMOKE TEST PASSED

Warnings:
- Never commit `.env`.
- Never paste API keys into prompts, GitHub, README, or screenshots.
- If a key is exposed, rotate it immediately.

## Windows TLS Troubleshooting

Update the local trust dependencies first:

```powershell
pip install --upgrade certifi truststore
```

Use the Windows trust store by default in `.env`:

```dotenv
TOSCO_USE_SYSTEM_TRUST_STORE=true
```

If TLS still fails:
- Export your trusted proxy or antivirus root CA as PEM.
- Set:

```dotenv
VULTR_CA_BUNDLE=C:\path\to\company-root-bundle.pem
```

Do not disable SSL verification.
