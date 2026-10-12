from django.db import migrations


def remove_legacy_columns(apps, schema_editor):
    table = schema_editor.quote_name("finance_financebudgetline")
    new_table = schema_editor.quote_name("finance_financebudgetline_cleanup")
    q = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute(f"DROP TABLE IF EXISTS {new_table}")
        cursor.execute(f"""
            CREATE TABLE {new_table} (
                id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                outcome varchar(255) NOT NULL,
                activity varchar(255) NOT NULL,
                justification text NOT NULL,
                budget_id bigint NOT NULL REFERENCES finance_financebudget (id) DEFERRABLE INITIALLY DEFERRED,
                code varchar(50) NOT NULL,
                description text NOT NULL,
                unit varchar(100) NOT NULL,
                price_per_unit decimal NOT NULL,
                units decimal NOT NULL,
                frequency decimal NOT NULL,
                CONSTRAINT unique_budget_line_code UNIQUE (budget_id, code)
            )
        """)
        cursor.execute(f"""
            INSERT INTO {new_table}
                (id, outcome, activity, justification, budget_id, code,
                 description, unit, price_per_unit, units, frequency)
            SELECT id, outcome, activity, justification, budget_id, code,
                   description, unit, price_per_unit, units, frequency
            FROM {table}
        """)
        cursor.execute(f"DROP TABLE {table}")
        cursor.execute(f"ALTER TABLE {new_table} RENAME TO {q('finance_financebudgetline')}")
        cursor.execute("PRAGMA foreign_keys=ON")


class Migration(migrations.Migration):
    dependencies = [("finance", "0023_remove_monthly_budget_columns")]

    operations = [
        migrations.RunPython(remove_legacy_columns, migrations.RunPython.noop),
    ]
