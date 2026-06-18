# -*- coding: utf-8 -*-
"""Controller: halaman public read-only untuk detail pesanan.

Route: /shop/order/<int:order_id>/<string:access_token>
- Public (auth='public') — siapapun dengan link+token bisa lihat
- Read-only — tidak ada button/action/form
- Akses ditolak kalau token tidak match
"""

import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WhatsappPublicOrderController(http.Controller):

    @http.route('/shop/order/<int:order_id>/<string:access_token>',
                type='http', auth='public', website=True, sitemap=False)
    def public_order_view(self, order_id, access_token, **kwargs):
        """Halaman public read-only detail pesanan.

        - Verifikasi access_token match dengan sale.order.access_token
        - Render template minimal: order info, items, total, status
        - Tidak ada tombol edit/cancel/pay
        """
        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists():
            return request.not_found()

        # Cek token
        expected_token = order.access_token or ''
        if not expected_token or expected_token != access_token:
            return request.not_found()

        # Format lines (skip section/note lines)
        lines = []
        for line in order.order_line:
            if line.display_type:
                continue
            lines.append({
                'name': line.product_id.name or line.name,
                'qty': line.product_uom_qty,
                'price_unit': line.price_unit,
                'subtotal': line.price_subtotal,
            })

        # Tentukan status display
        state_map = {
            'draft': 'Draft',
            'sent': 'Quotation Sent',
            'sale': 'Confirmed',
            'done': 'Done',
            'cancel': 'Cancelled',
        }
        state_label = state_map.get(order.state, order.state)

        # Metode pembayaran (kalau ada)
        payment_method = ''
        try:
            tx = order.transaction_ids[0]
            code = tx.provider_id.code if tx and tx.provider_id else ''
            if code == 'qris_dinamis':
                payment_method = 'QRIS'
            elif code == 'cod':
                payment_method = 'COD (Bayar di Tempat)'
            elif code:
                payment_method = code.upper()
        except Exception:
            pass

        values = {
            'order': order,
            'lines': lines,
            'state_label': state_label,
            'payment_method': payment_method,
            'company': order.company_id,
        }
        return request.render('whatsapp_evolution_notification.public_order_view', values)
