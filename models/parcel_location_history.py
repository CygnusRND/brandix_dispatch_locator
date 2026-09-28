# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class BrandixDocketParcelLocationHistory(models.Model):
    _name = 'brandix.docket.parcel.location.history'
    _description = 'Docket Parcel Location Audit Trail'
    _order = 'change_date desc, id desc'

    parcel_location_id = fields.Many2one(
        'brandix.docket.parcel.location',
        string="Cut Parcel Reference",
        ondelete='cascade',
        index=True
    )
    component_receipt_line_id = fields.Many2one(
        'brandix.component.receipt.line',
        string="Component Parcel Reference",
        ondelete='cascade',
        index=True
    )
    parcel_type = fields.Selection([
        ('cut', 'Cut Panel Parcel'),
        ('trim', 'Trims Parcel'),
        ('emb', 'Embellishment Parcel')
    ], string="Parcel Type", default='cut', index=True)

    picking_id = fields.Many2one(
        'stock.picking',
        string="Docket GRN",
        related='parcel_location_id.picking_id',
        readonly=True
    )
    docket_id = fields.Many2one(
        'product.template',
        string="Docket Master",
        index=True
    )
    component_receipt_id = fields.Many2one(
        'brandix.component.receipt',
        string="Component GRN",
        related='component_receipt_line_id.receipt_id',
        readonly=True
    )
    parcel_number = fields.Integer(string="Parcel #")
    parcel_name = fields.Char(string="Parcel Name")
    old_location_id = fields.Many2one(
        'stock.location',
        string="Previous Rack / Bin",
        domain="[('usage', '=', 'internal')]"
    )
    new_location_id = fields.Many2one(
        'stock.location',
        string="New Rack / Bin",
        domain="[('usage', '=', 'internal')]"
    )
    old_location_name = fields.Char(string="Previous Location Name")
    new_location_name = fields.Char(string="New Location Name")
    user_id = fields.Many2one(
        'res.users',
        string="Changed By",
        default=lambda self: self.env.user,
        index=True
    )
    change_date = fields.Datetime(
        string="Changed On",
        default=fields.Datetime.now,
        index=True
    )
    notes = fields.Char(string="Notes / Source")


class BrandixDocketParcelLocation(models.Model):
    _inherit = 'brandix.docket.parcel.location'

    history_ids = fields.One2many(
        'brandix.docket.parcel.location.history',
        'parcel_location_id',
        string="Location History"
    )
    history_count = fields.Integer(
        string="History Count",
        compute='_compute_history_count'
    )

    @api.depends('history_ids')
    def _compute_history_count(self):
        for rec in self:
            rec.history_count = len(rec.history_ids)

    def write(self, vals):
        if self.env.context.get('skip_history_create'):
            return super().write(vals)
        if 'location_dest_id' in vals:
            History = self.env['brandix.docket.parcel.location.history'].sudo()
            Location = self.env['stock.location'].sudo()
            new_loc_id = vals.get('location_dest_id')
            new_loc = Location.browse(new_loc_id) if new_loc_id else False
            new_loc_name = new_loc.display_name if new_loc else 'Unassigned'

            for rec in self:
                old_loc_id = rec.location_dest_id.id if rec.location_dest_id else False
                if old_loc_id != new_loc_id:
                    old_loc_name = rec.location_dest_id.display_name if rec.location_dest_id else 'Unassigned'
                    docket = rec.picking_id.docket_id if rec.picking_id else False
                    History.create({
                        'parcel_location_id': rec.id,
                        'parcel_number': rec.parcel_number,
                        'parcel_name': rec.parcel_name or f"Parcel #{rec.parcel_number}",
                        'docket_id': docket.id if docket else False,
                        'old_location_id': old_loc_id,
                        'new_location_id': new_loc_id,
                        'old_location_name': old_loc_name,
                        'new_location_name': new_loc_name,
                        'user_id': self.env.user.id,
                        'change_date': fields.Datetime.now(),
                        'notes': self.env.context.get('location_change_reason') or 'Location reassignment'
                    })
        return super().write(vals)

    def action_view_history(self):
        self.ensure_one()
        return {
            'name': _('Location History for %s') % (self.parcel_name or f"Parcel #{self.parcel_number}"),
            'type': 'ir.actions.act_window',
            'res_model': 'brandix.docket.parcel.location.history',
            'view_mode': 'list,form',
            'domain': [('parcel_location_id', '=', self.id)],
            'target': 'current',
        }


class BrandixComponentReceiptLine(models.Model):
    _inherit = 'brandix.component.receipt.line'

    history_ids = fields.One2many(
        'brandix.docket.parcel.location.history',
        'component_receipt_line_id',
        string="Location History"
    )
    history_count = fields.Integer(
        string="History Count",
        compute='_compute_history_count'
    )

    @api.depends('history_ids')
    def _compute_history_count(self):
        for rec in self:
            rec.history_count = len(rec.history_ids)

    def write(self, vals):
        if self.env.context.get('skip_history_create'):
            return super().write(vals)
        if 'location_id' in vals:
            History = self.env['brandix.docket.parcel.location.history'].sudo()
            Location = self.env['stock.location'].sudo()
            new_loc_id = vals.get('location_id')
            new_loc = Location.browse(new_loc_id) if new_loc_id else False
            new_loc_name = new_loc.display_name if new_loc else 'Unassigned'

            for rec in self:
                old_loc_id = rec.location_id.id if rec.location_id else False
                if old_loc_id != new_loc_id:
                    old_loc_name = rec.location_id.display_name if rec.location_id else 'Unassigned'
                    p_type = rec.receipt_id.component_type if rec.receipt_id else 'trim'
                    rec_name = rec.receipt_id.name if rec.receipt_id else ''
                    p_name = f"{'Trims' if p_type == 'trim' else 'EMB'} Parcel #{rec.parcel_no} ({rec_name})"
                    History.create({
                        'component_receipt_line_id': rec.id,
                        'parcel_type': p_type,
                        'parcel_number': rec.parcel_no,
                        'parcel_name': p_name,
                        'docket_id': rec.receipt_id.docket_id.id if rec.receipt_id and rec.receipt_id.docket_id else False,
                        'old_location_id': old_loc_id,
                        'new_location_id': new_loc_id,
                        'old_location_name': old_loc_name,
                        'new_location_name': new_loc_name,
                        'user_id': self.env.user.id,
                        'change_date': fields.Datetime.now(),
                        'notes': self.env.context.get('location_change_reason') or 'Component Location reassignment'
                    })
        return super().write(vals)

    def action_view_history(self):
        self.ensure_one()
        p_type = self.receipt_id.component_type if self.receipt_id else 'trim'
        return {
            'name': _('Location History for %s') % (f"{'Trims' if p_type == 'trim' else 'EMB'} Parcel #{self.parcel_no}"),
            'type': 'ir.actions.act_window',
            'res_model': 'brandix.docket.parcel.location.history',
            'view_mode': 'list,form',
            'domain': [('component_receipt_line_id', '=', self.id)],
            'target': 'current',
        }

