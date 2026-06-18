# -*- coding: utf-8 -*-
"""Controller: halaman public untuk detail pesanan + feedback form.

Routes:
- GET  /shop/order/<int:order_id>/<string:access_token>
       Halaman public read-only detail pesanan.
- GET  /shop/feedback/<int:order_id>/<string:access_token>
       Form feedback (rating bintang + catatan + permintaan menu baru).
- POST /shop/feedback/<int:order_id>/<string:access_token>
       Submit feedback, simpan ke whatsapp.order.feedback, tampilkan thank-you.
"""

import logging
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WhatsappPublicOrderController(http.Controller):

    # ============================================================
    # Public read-only order detail page
    # ============================================================

    @http.route('/shop/order/<int:order_id>/<string:access_token>',
                type='http', auth='public', website=True, sitemap=False)
    def public_order_view(self, order_id, access_token, **kwargs):
        """Halaman public read-only detail pesanan."""
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

    # ============================================================
    # Feedback form (GET) + submit (POST)
    # ============================================================

    def _get_order_or_404(self, order_id, access_token):
        """Helper: ambil sale.order + verifikasi token. Return None kalau 404."""
        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists():
            return None
        expected = order.access_token or ''
        if not expected or expected != access_token:
            return None
        return order

    @http.route('/shop/feedback/<int:order_id>/<string:access_token>',
                type='http', auth='public', website=True, sitemap=False, methods=['GET'])
    def feedback_form(self, order_id, access_token, **kwargs):
        """Tampilkan form feedback (rating bintang + catatan)."""
        order = self._get_order_or_404(order_id, access_token)
        if not order:
            return request.not_found()

        Feedback = request.env['whatsapp.order.feedback'].sudo()
        existing = Feedback.search([('sale_order_id', '=', order_id)], limit=1)

        if existing:
            return request.render(
                'whatsapp_evolution_notification.feedback_already_submitted',
                {'order': order, 'feedback': existing},
            )

        return request.render(
            'whatsapp_evolution_notification.feedback_form',
            {
                'order': order,
                'access_token': access_token,
                'error': kwargs.get('error'),
                'submitted': {},
            },
        )

    @http.route('/shop/feedback/<int:order_id>/<string:access_token>',
                type='http', auth='public', website=True, sitemap=False, methods=['POST'], csrf=False)
    def feedback_submit(self, order_id, access_token, **post):
        """Submit feedback, simpan ke DB, tampilkan thank-you."""
        order = self._get_order_or_404(order_id, access_token)
        if not order:
            return request.not_found()

        Feedback = request.env['whatsapp.order.feedback'].sudo()
        existing = Feedback.search([('sale_order_id', '=', order_id)], limit=1)
        if existing:
            # Sudah pernah submit, redirect ke halaman already-submitted
            return request.redirect('/shop/feedback/%d/%s' % (order_id, access_token))

        # Parse & validate rating
        try:
            rating_delivery = int(post.get('rating_delivery', 0) or 0)
            rating_food = int(post.get('rating_food', 0) or 0)
        except (TypeError, ValueError):
            rating_delivery = 0
            rating_food = 0

        if rating_delivery not in (1, 2, 3, 4, 5) or rating_food not in (1, 2, 3, 4, 5):
            return request.render(
                'whatsapp_evolution_notification.feedback_form',
                {
                    'order': order,
                    'access_token': access_token,
                    'error': 'Rating harus 1-5 bintang untuk kedua kategori.',
                    'submitted': post,
                },
            )

        menu_request = post.get('menu_request', 'enough')
        if menu_request not in ('enough', 'new'):
            menu_request = 'enough'

        feedback_text = (post.get('feedback_text') or '').strip()
        menu_request_text = ''
        if menu_request == 'new':
            menu_request_text = (post.get('menu_request_text') or '').strip()

        try:
            feedback = Feedback.create({
                'sale_order_id': order_id,
                'rating_delivery': rating_delivery,
                'rating_food': rating_food,
                'feedback_text': feedback_text,
                'menu_request': menu_request,
                'menu_request_text': menu_request_text,
            })
        except Exception as e:
            _logger.exception("[Feedback] Failed create for order %s: %s", order.name, e)
            return request.render(
                'whatsapp_evolution_notification.feedback_form',
                {
                    'order': order,
                    'access_token': access_token,
                    'error': 'Terjadi kesalahan saat menyimpan feedback. Mohon coba lagi.',
                    'submitted': post,
                },
            )

        return request.render(
            'whatsapp_evolution_notification.feedback_thankyou',
            {'order': order, 'feedback': feedback},
        )
