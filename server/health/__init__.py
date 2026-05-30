from server.health.sheets_check import check_sheets
from server.health.airtable_check import check_airtable


async def run_all_checks() -> dict[str, object]:
    sheets_ok = await check_sheets()
    airtable_ok = await check_airtable()
    status = "ok" if sheets_ok and airtable_ok else "degraded"
    return {"status": status, "sheetsOk": sheets_ok, "airtableOk": airtable_ok}
