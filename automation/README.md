# IP12 Automation (n8n) · v0.1 basic

Two separate n8n workflows:

| Workflow | File | Trigger | Writes to |
|---|---|---|---|
| **A · Weekly WP Commit** | `workflows/weekly-wp-commit.json` | Every Friday 17:00 | Google Sheet (Changelog + Snapshot), optional email |
| **B · YOLO Ingest** | `workflows/yolo-ingest.json` | Webhook `POST /ip12/yolo` | Postgres table `detections` |

```
WP1 YOLO (Python) ──POST──▶ n8n webhook ──▶ validate ──▶ Postgres: detections
Google Sheet (WP tasks) ──▶ n8n weekly diff ──▶ git-style changelog
```

## Folder

```
automation/
├── docker-compose.yml        n8n + Postgres for local testing
├── .env.example              copy to .env, set the password
├── sql/001_schema.sql        tables: runs, detections, evaluations, wp_changelog
├── workflows/                import these into n8n
└── scripts/send_test_detection.py   fake YOLO sender for testing
```

## Setup on Windows (about 30 min)

1. Install **Docker Desktop**. In Settings → Resources → Advanced, set the disk image location to `E:\Docker`.
2. Clone this repo to the E: drive:
   ```powershell
   cd E:\
   git clone https://github.com/HoangPham1234/IP12-ABB-AI-intergrated-project.git
   cd E:\IP12-ABB-AI-intergrated-project\automation
   copy .env.example .env
   ```
3. Open `.env` and change `POSTGRES_PASSWORD`.
4. Start it:
   ```powershell
   docker compose up -d
   ```
   The tables are created automatically on the first start.
5. Open http://localhost:5678 and create your n8n owner account.

## Test workflow B (YOLO → SQL)

1. n8n → **Workflows → Import from File** → `workflows/yolo-ingest.json`.
2. Open the **Insert into detections** node → Credential → *Create new* (Postgres):
   - Host `postgres` · Port `5432` · Database `ip12` · User `ip12` · Password = the one from `.env`
3. Click **Execute workflow** (it now listens for a test event).
4. In PowerShell:
   ```powershell
   python scripts\send_test_detection.py
   ```
   Expected: `HTTP 200` and the saved rows printed back.
5. Check the database:
   ```powershell
   docker compose exec postgres psql -U ip12 -c "SELECT id, run_code, class, confidence, model_version FROM detections;"
   ```
6. When it works, toggle the workflow **Active** and use `--prod`:
   ```powershell
   python scripts\send_test_detection.py --prod --count 20
   ```

### Data format WP1 sends

```json
{
  "run_code": "run-001",
  "model_version": "v1_2026-11-05",
  "detections": [
    { "frame_id": 12, "box_id": "box_003", "class": "box_small",
      "confidence": 0.91, "x": 410, "y": 220, "w": 120, "h": 95 }
  ]
}
```
Required for each detection: `class` and `confidence` (0 to 1). Bad rows are skipped and logged; the good ones are still saved.
WP1 can copy `send_detections()` from `scripts/send_test_detection.py` into the YOLO script.

## Test workflow A (Weekly WP)

1. Google Sheet with tabs **Tasks**, **Snapshot**, **Changelog**:
   - Tasks / Snapshot: `WP | ID | Task | Owner | Deliverable | Dependency | Status | Note`
   - Changelog: `Week | Date | Hash | Type | ID | Message | Owner`
   - Format the **ID** column as *Plain text*.
2. Import `workflows/weekly-wp-commit.json`, paste the sheet URL into the 4 Sheets nodes, connect Google.
3. In **GitHub Commits**, set `OWNER/REPO` to `HoangPham1234/IP12-ABB-AI-intergrated-project`.
4. Click **Run manually**. The first run logs "Initial commit: WP baseline".

## Roadmap

- [x] v0.1 YOLO → SQL ingest, weekly WP commit log
- [ ] Low-confidence alert → Discord
- [ ] Evaluation Google Form → `evaluations`
- [ ] Weekly AI stats report
- [ ] Missing-update reminder email
- [ ] Weekly WP log also saved to `wp_changelog`
