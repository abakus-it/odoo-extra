# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MigrabotVersion(models.Model):
    _name = 'migrabot.version'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    parent_id = fields.Many2one(comodel_name='migrabot.version')
    active = fields.Boolean(default=True)
