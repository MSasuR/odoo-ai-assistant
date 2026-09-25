from pydantic_settings import BaseSettings, SettingsConfigDict


def csv_set(value: str) -> set[str]:
    """Parse a comma-separated env value into a set of Odoo group XML ids."""
    return {item.strip() for item in value.split(",") if item.strip()}


class Settings(BaseSettings):
    # Reads real environment variables first, then a local .env file (ignored by git).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o-mini"

    # Read-only connection to the Odoo database (role `ai_readonly`, schema `ai`).
    odoo_db_dsn: str
    # pgvector database for document chunks and the usage log.
    vector_db_dsn: str
    # Shared secret used to sign/verify the identity token issued by the Odoo module.
    hmac_secret: str

    # Odoo groups (XML ids, comma separated) that unlock each tool family. Defaults are
    # standard Odoo groups; implied groups are already expanded by the Odoo controller,
    # so listing the base group is enough. Override them for custom security models.
    sales_groups: str = "sales_team.group_sale_salesman,sales_team.group_sale_manager"
    invoice_groups: str = (
        "account.group_account_invoice,account.group_account_user,account.group_account_manager"
    )
    hr_viewer_groups: str = (
        "hr_holidays.group_hr_holidays_responsible,hr_holidays.group_hr_holidays_manager,hr.group_hr_manager"
    )


settings = Settings()
