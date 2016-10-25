# -*- coding: utf-8 -*-
{
    'name': 'Runbot',
    'category': 'Website',
    'summary': 'Runbot',
    'version': '1.2',
    'description': "Runbot",
    'author': 'OpenERP SA',
    'depends': ['website'],
    'external_dependencies': {
        'python': ['matplotlib'],
    },
    'data': [
        'data/runbot_data.xml',
        'security/runbot_security.xml',
        'security/ir.model.access.csv',
        'security/ir.rule.csv',
        'views/runbot_views.xml',
        'views/runbot_templates.xml',
        'views/res_config_view.xml',
    ],
    'installable': True,
}
