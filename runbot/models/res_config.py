# -*- coding: utf-8 -*-
from odoo import models, fields


class RunbotConfigSettings(models.TransientModel):
    _name = 'runbot.config.settings'
    _inherit = 'res.config.settings'

    default_workers = fields.Integer('Total Number of Workers')
    default_running_max = fields.Integer('Maximum Number of Running Builds')
    default_timeout = fields.Integer('Default Timeout (in seconds)')
    default_starting_port = fields.Integer('Starting Port for Running Builds')
    default_domain = fields.Char('Runbot Domain')

    def get_default_parameters(self):
        IrConfigParameter = self.env['ir.config.parameter']
        return {'default_workers': int(IrConfigParameter.get_param('runbot.workers', default=6)),
                'default_running_max': int(IrConfigParameter.get_param('runbot.running_max', default=75)),
                'default_timeout': int(IrConfigParameter.get_param('runbot.timeout', default=1800)),
                'default_starting_port': int(IrConfigParameter.get_param('runbot.starting_port', default=2000)),
                'default_domain': IrConfigParameter.get_param('runbot.domain', default='runbot.odoo.com'),
                }

    def set_default_parameters(self):
        IrConfigParameter = self.env['ir.config_parameter']
        IrConfigParameter.set_param('runbot.workers', self.default_workers)
        IrConfigParameter.set_param('runbot.running_max', self.default_running_max)
        IrConfigParameter.set_param('runbot.timeout', self.default_timeout)
        IrConfigParameter.set_param('runbot.starting_port', self.default_starting_port)
        IrConfigParameter.set_param('runbot.domain', self.default_domain)
