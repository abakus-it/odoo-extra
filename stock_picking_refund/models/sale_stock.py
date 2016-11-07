# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import api, fields, models

import logging
_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.multi
    def _get_delivered_qty(self):
        """Computes the delivered quantity on sale order lines, based on done stock moves related to its procurements
        """
        self.ensure_one()
        qty = super(SaleOrderLine, self)._get_delivered_qty()
        for move in self.procurement_ids.mapped('move_ids').filtered(lambda r: r.state == 'done' and not r.scrapped):
            if move.location_dest_id.usage == "internal" and move.to_refund_so:
                qty -= self.env['product.uom']._compute_qty_obj(move.product_uom, move.product_uom_qty, self.product_uom)
        return qty

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # Inherit this method, copy-paste from old code while adding mine
    @api.depends('order_id.state', 'move_ids.state')
    def _compute_qty_received(self):
        """Computes the delivered quantity on purchase order lines, based on done stock moves related to its procurements
        """
        for line in self:
            # Purchase order is not confirmed or done
            if line.order_id.state not in ['purchase', 'done']:
                line.qty_received = 0.0
                continue
            # Product is service
            if line.product_id.type not in ['consu', 'product']:
                line.qty_received = line.product_qty
                continue
            # BOM
            bom_delivered = self.sudo()._get_bom_delivered(line.sudo())
            if bom_delivered and any(bom_delivered.values()):
                total = line.product_qty
            elif bom_delivered:
                total = 0.0
            else:
                total = 0.0
                for move in line.move_ids:
                    if move.state == 'done' and not move.scrapped:
                        if move.product_uom != line.product_uom and not move.to_refund_so:
                            total += productuom._compute_qty_obj(move.product_uom, move.product_uom_qty, line.product_uom)
                        # OUT made by a reverse on the IN from PO
                        elif move.location_id.usage == "internal" and move.to_refund_so:
                            total -= self.env['product.uom']._compute_qty_obj(move.product_uom, move.product_uom_qty, self.product_uom)
                        else:
                            total += move.product_uom_qty
            line.qty_received = total

class StockMove(models.Model):
    _inherit = "stock.move"

    to_refund_so = fields.Boolean(string="To Refund in SO/PO", default=False,
                                  help='Trigger a decrease of the delivered quantity in the associated Sale Order')

class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    @api.multi
    def _create_returns(self):
        new_picking_id, pick_type_id = super(StockReturnPicking, self)._create_returns()
        new_picking = self.env['stock.picking'].browse([new_picking_id])
        for move in new_picking.move_lines:
            return_picking_line = self.product_return_moves.filtered(lambda r: r.move_id == move.origin_returned_move_id)
            # We have to set the purchase_line_id here because we want the move to be associated to the PO line
            # if not, the delivery quantity will not be correct
            if move.origin_returned_move_id.purchase_line_id:
                move.purchase_line_id = move.origin_returned_move_id.purchase_line_id
            if return_picking_line and return_picking_line.to_refund_so:
                move.to_refund_so = True

        return new_picking_id, pick_type_id


class StockReturnPickingLine(models.TransientModel):
    _inherit = "stock.return.picking.line"

    to_refund_so = fields.Boolean(string="To Refund in SO/PO", help='Trigger a decrease of the delivered quantity in the associated Sale Order')
