# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProjectIssue(models.Model):
    _inherit = 'project.issue'

    is_migration = fields.Boolean(string="Migration ticket")
    database_name = fields.Char(required=True, index=True, string="Database Name")
    prod_migration_date = fields.Datetime(string="Final migration date")
    recipes_ids = fields.One2many(comodel_name='migrabot.recipe', inverse_name='issue_id')
    last_test_date = fields.Datetime()
    last_migration_status = fields.Selection([('ok', 'OK'), ('ko', 'ko')], index=True)
    last_migration_duration = fields.Integer(help='(in minutes)')

    def action_launch_migration(self):
        for record in self:
            pass

    def print_recipes(self)
        for record in self:
            pass


# Theoretical flow of a migration request:
# - NEW
#   * basic information
# - PRE ANALYSIS stage:
#   * fetch database
#   * compute custom score + add the report
# - MIGRATION / MIGRATION 2 stage
#   * while != ok
#   * try to migrate -> ok or ko
#   * write recipes if needed
#   * launch automated testing
# -  CUSTOMER FEEDBACK
#   * while != ok
#   * write post recipes
#   * if 2nd mig is needed go back to MIGRATION 2 stage
#   * if ok go to PRODUCTION
#   * if no customer feedback in 1 month, go to CANCELLED
# - PRODUCTION
#   * print all recipes if needed
#   * plan migration date (need calendar)
#   * don't forget to backup
#   * move to done
# - DONE
# - CANCELLED

