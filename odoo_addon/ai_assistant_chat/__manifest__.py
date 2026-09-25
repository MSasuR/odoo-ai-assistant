# -*- coding: utf-8 -*-
{
    'name': 'AI Assistant Chat',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Chat with an AI assistant (RAG + live Odoo data) embedded in the top bar',
    'description': """
A systray chat that talks to the assistant API (FastAPI). Odoo signs an HMAC token with the
identity of the current user (uid, employee, companies, groups) and acts as a proxy, so the
secret and the identity never pass through the browser.
""",
    'author': 'MSasuR',
    'license': 'LGPL-3',
    'depends': ['base_setup', 'web', 'hr'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_assistant_chat/static/src/chat/*.js',
            'ai_assistant_chat/static/src/chat/*.xml',
            'ai_assistant_chat/static/src/chat/*.scss',
        ],
    },
    'installable': True,
    'application': False,
}
