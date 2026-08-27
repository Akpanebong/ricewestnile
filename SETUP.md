# RiceWestNile setup guide

 Setup instructions for another device

1. Clone the repo.
2. Create and activate a virtual environment.
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS/Linux
   # or .venv\Scripts\activate   # Windows
   ```
3. Install the project dependencies.
   ```bash
   pip install -r requirements.txt
   ```
   - This installs core runtime dependencies including Django and `python-dateutil` (required by `core/project_models.py` and `mne/monitoring/models.py`).
4. Set the database environment if needed.
   - By default, the app uses SQLite (`enterprise/settings.py`):
     ```bash
     export DB_ENGINE=django.db.backends.sqlite3
     export DB_NAME=db.sqlite3
     ```
   - You can also point it to PostgreSQL/MySQL by setting `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`.
5. Apply migrations:
   ```bash
   python manage.py migrate
   ```
6. Start the app:
   ```bash
   python manage.py runserver
   ```

## Recommended verification

Run the following after pulling the fix:

```bash
python manage.py check
python manage.py migrate
python manage.py runserver
```

If all three commands complete without error, the project is ready to start on a new machine.
