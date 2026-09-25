"""Configure the AI Assistant module inside Odoo (run through `odoo shell`, see setup_demo.sh)."""
import os

icp = env["ir.config_parameter"].sudo()  # noqa: F821 - `env` is provided by odoo shell
icp.set_param("ai_assistant_chat.url", "http://assistant:8000")
icp.set_param("ai_assistant_chat.secret", os.environ["HMAC_SECRET"])
env.cr.commit()  # noqa: F821
print("CONFIGURED: url and secret stored in ir.config_parameter")
