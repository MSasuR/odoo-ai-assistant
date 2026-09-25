from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ai_assistant_url = fields.Char(
        string='Assistant API URL',
        config_parameter='ai_assistant_chat.url',
        default='http://assistant:8000',
    )
    ai_assistant_secret = fields.Char(
        string='Signing secret (HMAC)',
        config_parameter='ai_assistant_chat.secret',
        help='Must be the same HMAC_SECRET used by the assistant service.',
    )
