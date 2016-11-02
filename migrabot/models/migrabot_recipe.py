# -*- coding: utf-8 -*-
import sqlparse

from odoo import models, fields, api, _


class MigrabotRecipe(models.Model):
    _name = 'migrabot.recipe'
    _order = 'id desc, sequence asc'

    apply_when = fields.Selection([('pre', 'pre'), ('post', 'post')])
    version = fields.Many2one(comodel_name='migrabot.version', required=True)
    issue_id = fields.Many2one(comodel_name='project.issue', required=True, domain=[('is_migration', '=', True)], ondelete='cascade')
    recipe_type = fields.Selection([('manual', 'Manual action'), ('sql', 'SQL code')])
    sequence = fields.Integer(required=True, default=100000)

    comments = fields.Text()
    sql = fields.Text()
