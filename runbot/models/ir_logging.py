# -*- coding: utf-8 -*-
from odoo import models, fields


class IrLogging(models.Model):
    _inherit = 'ir.logging'
    _order = 'id'

    build_id = fields.Many2one('runbot.build', 'Build')
    type = fields.Selection([('client', 'CLIENT'),
                             ('server', 'SERVER'),
                             ('runbot', 'RUNBOT')],
                            string='Type', required=True, index=True)
