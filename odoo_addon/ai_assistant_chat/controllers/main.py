import logging

import requests
from odoo import _, http
from odoo.exceptions import AccessError
from odoo.http import request

from ..lib import sign_token

_logger = logging.getLogger(__name__)

TIMEOUT = 90  # seconds: the LLM may chain several calls


class AiAssistantController(http.Controller):

    def _identity(self, user):
        """Identity signed into the token. Groups = all of them, implied ones included
        (a sales manager inherits the salesman group)."""
        xmlids = user.all_group_ids._get_external_ids()
        groups = sorted({x for ids in xmlids.values() for x in ids})
        return {
            'uid': user.id,
            'employee_id': user.sudo().employee_id.id or None,
            'company_ids': user.company_ids.ids,
            'groups': groups,
        }

    @http.route('/ai_assistant/chat', type='jsonrpc', auth='user', methods=['POST'])
    def chat(self, message, conversation_id=None):
        user = request.env.user
        if not user._is_internal():
            raise AccessError(_("The assistant is only available to internal users."))

        icp = request.env['ir.config_parameter'].sudo()
        url = (icp.get_param('ai_assistant_chat.url') or '').rstrip('/')
        secret = icp.get_param('ai_assistant_chat.secret')
        if not url or not secret:
            return {'error': _("The assistant is not configured. Ask an administrator to fill in "
                               "Settings → AI Assistant.")}

        token = sign_token(self._identity(user), secret)
        body = {'message': message}
        if conversation_id:
            body['conversation_id'] = conversation_id
        try:
            r = requests.post(f'{url}/chat', json=body, timeout=TIMEOUT,
                              headers={'Authorization': f'Bearer {token}'})
        except requests.RequestException:
            _logger.exception("Could not reach the assistant API")
            return {'error': _("Could not reach the assistant. Please try again in a moment.")}

        if r.status_code == 429:
            return {'error': _("You are sending too many requests. Please wait a moment.")}
        if r.status_code == 422:
            return {'error': _("The question is not valid (is it empty or longer than 2000 characters?).")}
        if r.status_code == 401:
            # The secret in Settings does not match the API's: a configuration error.
            _logger.error("The API rejected the token: the secret in Settings → AI Assistant does not match")
            return {'error': _("The assistant is misconfigured. Please tell an administrator.")}
        if r.status_code != 200:
            _logger.warning("Assistant API answered %s", r.status_code)
            return {'error': _("The assistant is not available right now. Please try again.")}
        data = r.json()
        return {
            'answer': data['answer'],
            'conversation_id': data['conversation_id'],
            'sources': data.get('sources', []),
            'tools_used': data.get('tools_used', []),
        }
