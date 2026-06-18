# -*- coding: utf-8 -*-
"""Model: whatsapp.order.feedback

Menyimpan feedback customer setelah pesanan selesai.
Field:
- sale_order_id : link ke sale.order (unique, 1 order = 1 feedback)
- partner_id    : denormalized dari sale_order (untuk audit)
- rating_delivery : 1-5 (bintang pengiriman)
- rating_food     : 1-5 (bintang makanan)
- feedback_text   : kolom bebas (catatan customer)
- menu_request    : selection 'enough' / 'new'
- menu_request_text : jika 'new', tulisan usulan menu baru
- submitted_at    : timestamp submit
- state           : denormalized dari sale_order.state (info saja)

Akses:
- Public bisa create (via controller /shop/feedback/<id>/<token>)
- Sales manager bisa read/manage
- Salesman read-only
"""

from odoo import api, fields, models, _


class WhatsappOrderFeedback(models.Model):
    _name = 'whatsapp.order.feedback'
    _description = 'Customer Feedback for Completed Order'
    _order = 'submitted_at desc'
    _rec_name = 'sale_order_id'

    sale_order_id = fields.Many2one(
        'sale.order', string='Order', required=True, ondelete='cascade', index=True,
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer',
        related='sale_order_id.partner_id', store=True, readonly=True,
    )
    order_name = fields.Char(
        string='No. Order',
        related='sale_order_id.name', store=True, readonly=True,
    )
    order_state = fields.Selection(
        string='Order State',
        related='sale_order_id.state', store=True, readonly=True,
    )
    rating_delivery = fields.Integer(
        string='Rating Pengiriman', required=True,
        help='1-5 bintang untuk kualitas pengiriman',
    )
    rating_food = fields.Integer(
        string='Rating Makanan', required=True,
        help='1-5 bintang untuk kualitas makanan',
    )
    feedback_text = fields.Text(string='Feedback')
    menu_request = fields.Selection(
        [
            ('enough', 'Sudah Cukup'),
            ('new', 'Ada Permintaan Menu Baru'),
        ],
        string='Permintaan Menu',
        default='enough',
        required=True,
    )
    menu_request_text = fields.Text(string='Usulan Menu Baru')
    submitted_at = fields.Datetime(
        string='Submitted At', default=fields.Datetime.now, readonly=True,
    )

    _sql_constraints = [
        ('unique_per_order',
         'unique(sale_order_id)',
         'Feedback untuk order ini sudah pernah disubmit.'),
    ]

    @api.constrains('rating_delivery', 'rating_food')
    def _check_rating_range(self):
        for rec in self:
            if not (1 <= rec.rating_delivery <= 5):
                raise ValueError(_('Rating Pengiriman harus antara 1-5.'))
            if not (1 <= rec.rating_food <= 5):
                raise ValueError(_('Rating Makanan harus antara 1-5.'))

    def name_get(self):
        res = []
        for rec in self:
            name = '%s - %s/5 Pengiriman, %s/5 Makanan' % (
                rec.order_name or rec.sale_order_id.name,
                rec.rating_delivery, rec.rating_food,
            )
            res.append((rec.id, name))
        return res

    def action_open_order(self):
        """Smart-button action: buka sale.order terkait."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Order',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
