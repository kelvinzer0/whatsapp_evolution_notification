# -*- coding: utf-8 -*-
"""Sale Order hooks: kirim WA saat status berubah.

Trigger:
- order_received: draft/sent -> sale (confirmed)         emoji: 🛒
- order_delivered: website_order_stage -> out_for_delivery  emoji: 🚚
- order_done: -> done (invoiced & closed)                emoji: ✅
- order_cancelled: -> cancelled                          emoji: ❌

Hanya trigger jika:
- Config master switch ON
- Trigger spesifik ON di config
- Customer punya nomor WA (mobile/phone)
- Order berasal dari website (website_sale) atau minimal ada partner_id

Format pesan: TO-THE-POINT, no greeting, langsung ke isi.
Emoji prefix sesuai status untuk memudahkan customer mengenali jenis update.
"""

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ============================================================
    # OVERRIDE: action_confirm -> order_received
    # ============================================================

    def action_confirm(self):
        """Hook order diterima. Kirim WA dengan detail order + URL portal."""
        res = super().action_confirm()
        for order in self:
            try:
                order._whatsapp_notify_order_received()
            except Exception as e:
                _logger.exception(
                    "[WA] Failed notify order_received for %s: %s",
                    order.name, e,
                )
        return res

    def action_cancel(self):
        """Hook order dibatalkan."""
        before_states = {so.id: so.state for so in self}
        res = super().action_cancel()
        for order in self:
            if before_states.get(order.id) == 'cancel':
                continue
            try:
                order._whatsapp_notify_order_cancelled()
            except Exception as e:
                _logger.exception(
                    "[WA] Failed notify order_cancelled for %s: %s",
                    order.name, e,
                )
        return res

    # ============================================================
    # HOOK: delivery & done via write()
    # - state -> 'done'                    => order_done
    # - website_order_stage -> 'out_for_delivery'  => order_delivered
    # ============================================================

    def write(self, vals):
        """Deteksi transisi:
        - state ke 'done' => trigger WA 'Pesanan Selesai'
        - website_order_stage ke 'out_for_delivery' => trigger WA 'Pesanan Dikirim'
        """
        before_state = {}
        before_stage = {}
        if 'state' in vals:
            before_state = {so.id: so.state for so in self}
        # website_order_stage mungkin tidak ada kalau website_sale_dashboard tdk terinstall
        if 'website_order_stage' in vals and self._fields.get('website_order_stage'):
            before_stage = {so.id: so.website_order_stage for so in self}

        res = super().write(vals)

        if 'state' in vals:
            for order in self:
                old = before_state.get(order.id)
                new = vals['state']
                if old != 'done' and new == 'done':
                    try:
                        order._whatsapp_notify_order_done()
                    except Exception as e:
                        _logger.exception(
                            "[WA] Failed notify order_done for %s: %s",
                            order.name, e,
                        )

        if 'website_order_stage' in vals and before_stage:
            new_stage = vals['website_order_stage']
            for order in self:
                old_stage = before_stage.get(order.id)
                if old_stage != 'out_for_delivery' and new_stage == 'out_for_delivery':
                    try:
                        order._whatsapp_notify_order_delivered()
                    except Exception as e:
                        _logger.exception(
                            "[WA] Failed notify order_delivered for %s: %s",
                            order.name, e,
                        )
        return res

    # ============================================================
    # PRIVATE: helpers
    # ============================================================

    def _whatsapp_is_trigger_enabled(self, config_key):
        """Cek apakah trigger aktif di config."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        master = ICP.get_param('whatsapp_evolution.enabled', 'True') == 'True'
        specific = ICP.get_param('whatsapp_evolution.' + config_key, 'True') == 'True'
        return master and specific

    def _whatsapp_get_partner_number(self):
        """Ambil nomor WA customer (mobile dulu, phone fallback)."""
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return ''
        return partner.mobile or partner.phone or ''

    def _whatsapp_get_portal_url(self):
        """URL public read-only untuk order ini.

        Format: {base}/shop/order/{order_id}/{access_token}
        access_token di-generate kalau belum ada (field bawaan website_sale).
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        base = (ICP.get_param('whatsapp_evolution.portal_base_url')
                or 'https://odoo.warunglakku.com').rstrip('/')
        if not self.access_token:
            self._generate_access_token_safe()
        return '%s/shop/order/%d/%s' % (base, self.id, self.access_token or 'NO_TOKEN')

    def _generate_access_token_safe(self):
        """Generate access_token kalau field ada (dari website_sale) dan masih kosong."""
        self.ensure_one()
        try:
            if hasattr(self, 'access_token') and self._fields.get('access_token'):
                if not self.access_token:
                    token = self._generate_access_token() if hasattr(self, '_generate_access_token') else None
                    if not token:
                        import secrets
                        token = secrets.token_urlsafe(16)
                    self.sudo().write({'access_token': token})
        except Exception as e:
            _logger.warning("Failed generate access_token for SO %s: %s", self.name, e)

    def _whatsapp_get_store_name(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return ICP.get_param('whatsapp_evolution.store_name') or 'Warung Lakku'

    def _whatsapp_format_rupiah(self, amount):
        """Format angka ke Rupiah: 15000 -> 'Rp 15.000'."""
        try:
            return 'Rp ' + '{:,.0f}'.format(amount).replace(',', '.')
        except Exception:
            return str(amount)

    # ============================================================
    # BUILD TEXT
    # ============================================================

    def _whatsapp_build_order_received_text(self):
        """Pesan DETAIL untuk order diterima (initial message).

        Format to-the-point, no greeting, langsung ke isi.
        Emoji header 🛒 untuk menandai ini notifikasi order baru.
        """
        self.ensure_one()
        store = self._whatsapp_get_store_name()
        url = self._whatsapp_get_portal_url()

        lines_text = []
        for line in self.order_line:
            if line.display_type:
                continue
            name = line.product_id.name or line.name or ''
            qty = int(line.product_uom_qty) if line.product_uom_qty == int(line.product_uom_qty) else line.product_uom_qty
            price = self._whatsapp_format_rupiah(line.price_subtotal)
            lines_text.append('- %s x%d (%s)' % (name, qty, price))

        items = '\n'.join(lines_text) if lines_text else '(tidak ada item)'

        text = (
            "\U0001F6D2 Pesanan {order} di {store} telah diterima.\n\n"
            "No. Order: {order}\n"
            "Tanggal: {date}\n"
            "Metode: {payment}\n\n"
            "Item:\n{items}\n\n"
            "Total: {total}\n\n"
            "Detail: {url}"
        ).format(
            order=self.name,
            store=store,
            date=fields.Datetime.from_string(self.date_order).strftime('%d/%m/%Y %H:%M') if self.date_order else '',
            payment=self._get_payment_method_label(),
            items=items,
            total=self._whatsapp_format_rupiah(self.amount_total),
            url=url,
        )
        return text

    def _get_payment_method_label(self):
        """Label metode pembayaran dari provider QRIS/COD/other."""
        self.ensure_one()
        try:
            tx = self.transaction_ids[0]
            code = tx.provider_id.code if tx and tx.provider_id else ''
            if code == 'qris_dinamis':
                return 'QRIS'
            if code == 'cod':
                return 'COD (Bayar di Tempat)'
            if code:
                return code.upper()
        except Exception:
            pass
        return 'Online'

    def _whatsapp_build_status_update_text(self, emoji, status_label, extra_info=''):
        """Pesan UPDATE STATUS — singkat, no greeting, no URL.

        Format: '{emoji} Pesanan {order} - {status}' (+ extra_info kalau ada)

        :param emoji: emoji prefix (string), mis. '🚚', '✅', '❌'
        :param status_label: label status, mis. 'Pesanan Dikirim'
        :param extra_info: info tambahan opsional (alasan, catatan, dll)
        """
        self.ensure_one()
        text = "{emoji} Pesanan {order} - {status}".format(
            emoji=emoji,
            order=self.name,
            status=status_label,
        )
        if extra_info:
            text += '. ' + extra_info
        return text

    def _whatsapp_send_safe(self, trigger, text, payment_tx_id=False):
        """Wrapper: cek trigger enabled + kirim + log."""
        self.ensure_one()
        config_map = {
            'order_received': 'trigger_order_received',
            'order_delivered': 'trigger_order_delivered',
            'order_done': 'trigger_order_done',
            'order_cancelled': 'trigger_order_cancelled',
        }
        config_key = config_map.get(trigger)
        if not config_key:
            _logger.warning("[WA] Unknown trigger: %s", trigger)
            return False
        if not self._whatsapp_is_trigger_enabled(config_key):
            _logger.info("[WA] Trigger %s disabled, skip order %s", trigger, self.name)
            return False

        number = self._whatsapp_get_partner_number()
        if not number:
            _logger.info("[WA] No WA number for partner %s, skip order %s",
                         self.partner_id.display_name, self.name)
            return False

        self.env['whatsapp.message.log'].log_and_send(
            partner_id=self.partner_id.id,
            trigger=trigger,
            message_text=text,
            sale_order_id=self.id,
            payment_transaction_id=payment_tx_id,
            number_override=number,
        )
        return True

    # ============================================================
    # PUBLIC: trigger methods (dipanggil dari override di atas)
    # ============================================================

    def _whatsapp_notify_order_received(self):
        for order in self:
            if order.state != 'sale':
                continue
            text = order._whatsapp_build_order_received_text()
            order._whatsapp_send_safe('order_received', text)

    def action_test_send_whatsapp(self):
        """Manual test dari tombol di sale.order form."""
        for order in self:
            text = order._whatsapp_build_order_received_text()
            order._whatsapp_send_safe('order_received', text)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'WhatsApp',
                'message': 'Pesan dikirim (cek WhatsApp Logs untuk status).',
                'type': 'info',
                'sticky': False,
            },
        }

    def _whatsapp_notify_order_delivered(self):
        """Trigger: website_order_stage -> out_for_delivery (Pesanan Dikirim)."""
        for order in self:
            text = order._whatsapp_build_status_update_text(
                emoji='\U0001F69A',  # 🚚 delivery truck
                status_label='Pesanan Dikirim',
            )
            order._whatsapp_send_safe('order_delivered', text)

    def _whatsapp_notify_order_done(self):
        """Trigger: state -> done (Pesanan Selesai)."""
        for order in self:
            text = order._whatsapp_build_status_update_text(
                emoji='\u2705',  # ✅ check mark button
                status_label='Pesanan Selesai',
            )
            order._whatsapp_send_safe('order_done', text)

    def _whatsapp_notify_order_cancelled(self):
        """Trigger: state -> cancel (Pesanan Dibatalkan)."""
        for order in self:
            text = order._whatsapp_build_status_update_text(
                emoji='\u274C',  # ❌ cross mark
                status_label='Pesanan Dibatalkan',
            )
            order._whatsapp_send_safe('order_cancelled', text)
