# -*- coding: utf-8 -*-
"""Hook payment.transaction (QRIS + COD) untuk kirim WA.

Trigger:
- qris_pending_verification: user klik 'Saya sudah bayar' -> state pending_verification
- qris_paid: admin verify -> state paid
- qris_rejected: admin reject -> state rejected
- cod_waiting_delivery: COD tx created -> state waiting_delivery

Module ini INHERIT (tidak override total) action methods di parent module
(website_sale_payment_qris_cod). Pattern: super().method() lalu kirim WA.
"""

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # ============================================================
    # OVERRIDE: action_qris_user_confirm_paid
    # ============================================================

    def action_qris_user_confirm_paid(self):
        """User klik 'Saya sudah bayar' -> state pending_verification."""
        super().action_qris_user_confirm_paid()
        for tx in self:
            if tx.qris_state == 'pending_verification':
                try:
                    tx._whatsapp_notify_qris_pending_verification()
                except Exception as e:
                    _logger.exception("[WA] Failed notify qris_pending_verification for %s: %s",
                                      tx.reference, e)
        return True

    def action_qris_mark_paid(self, mutation_record=None):
        """Admin verify -> state paid."""
        super().action_qris_mark_paid(mutation_record=mutation_record)
        for tx in self:
            if tx.qris_state == 'paid':
                try:
                    tx._whatsapp_notify_qris_paid()
                except Exception as e:
                    _logger.exception("[WA] Failed notify qris_paid for %s: %s",
                                      tx.reference, e)
        return True

    def action_qris_reject(self, reason=''):
        """Admin reject -> state rejected."""
        super().action_qris_reject(reason=reason)
        for tx in self:
            if tx.qris_state == 'rejected':
                try:
                    tx._whatsapp_notify_qris_rejected(reason=reason)
                except Exception as e:
                    _logger.exception("[WA] Failed notify qris_rejected for %s: %s",
                                      tx.reference, e)
        return True

    def action_cod_mark_delivered(self):
        """Admin mark COD delivered."""
        super().action_cod_mark_delivered()
        for tx in self:
            if tx.cod_state == 'delivered':
                try:
                    tx._whatsapp_notify_cod_waiting_delivery()
                except Exception as e:
                    _logger.exception("[WA] Failed notify cod_delivered for %s: %s",
                                      tx.reference, e)
        return True

    # ============================================================
    # PRIVATE: build text + send
    # ============================================================

    def _whatsapp_is_trigger_enabled(self, config_key):
        ICP = self.env['ir.config_parameter'].sudo()
        master = ICP.get_param('whatsapp_evolution.enabled', 'True') == 'True'
        specific = ICP.get_param('whatsapp_evolution.' + config_key, 'True') == 'True'
        return master and specific

    def _whatsapp_get_partner_number(self):
        """Ambil nomor WA customer (partner dari sale_order atau partner_id tx)."""
        self.ensure_one()
        partner = self.partner_id
        if not partner and self.sale_order_ids:
            partner = self.sale_order_ids[0].partner_id
        if not partner:
            return ''
        return partner.mobile or partner.phone or ''

    def _whatsapp_get_partner_id(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner and self.sale_order_ids:
            partner = self.sale_order_ids[0].partner_id
        return partner.id if partner else False

    def _whatsapp_get_portal_url(self):
        """URL public read-only untuk sale order terkait."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        base = (ICP.get_param('whatsapp_evolution.portal_base_url')
                or 'https://odoo.warunglakku.com').rstrip('/')
        if self.sale_order_ids:
            so = self.sale_order_ids[0]
            # Generate token kalau belum ada (delegasikan ke sale.order method)
            if not so.access_token:
                so._generate_access_token_safe()
            return '%s/shop/order/%d/%s' % (base, so.id, so.access_token or 'NO_TOKEN')
        return base + '/shop'

    def _whatsapp_get_store_name(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return ICP.get_param('whatsapp_evolution.store_name') or 'Warung Lakku'

    def _whatsapp_format_rupiah(self, amount):
        try:
            return 'Rp ' + '{:,.0f}'.format(amount or 0).replace(',', '.')
        except Exception:
            return str(amount)

    def _whatsapp_send_safe(self, trigger, text):
        """Cek trigger enabled + kirim + log."""
        self.ensure_one()
        config_map = {
            'qris_pending_verification': 'trigger_qris_pending',
            'qris_paid': 'trigger_qris_paid',
            'qris_rejected': 'trigger_qris_rejected',
            'cod_waiting_delivery': 'trigger_cod_waiting',
        }
        config_key = config_map.get(trigger)
        if not config_key:
            return False
        if not self._whatsapp_is_trigger_enabled(config_key):
            _logger.info("[WA] Trigger %s disabled, skip tx %s", trigger, self.reference)
            return False

        number = self._whatsapp_get_partner_number()
        if not number:
            _logger.info("[WA] No WA number for partner of tx %s, skip", self.reference)
            return False

        sale_order_id = self.sale_order_ids[0].id if self.sale_order_ids else False
        self.env['whatsapp.message.log'].log_and_send(
            partner_id=self._whatsapp_get_partner_id(),
            trigger=trigger,
            message_text=text,
            sale_order_id=sale_order_id,
            payment_transaction_id=self.id,
            number_override=number,
        )
        return True

    # ============================================================
    # BUILD TEXT per trigger
    # ============================================================

    def _whatsapp_build_qris_pending_text(self):
        """Format singkat dengan emoji:
        '⏳ Pembayaran QRIS untuk order X menunggu verifikasi admin.'
        """
        self.ensure_one()
        so_name = self.sale_order_ids[0].name if self.sale_order_ids else self.reference
        return "\u23F3 Pembayaran QRIS untuk order {order} menunggu verifikasi admin.".format(
            order=so_name,
        )

    def _whatsapp_build_qris_paid_text(self):
        """Format singkat dengan emoji:
        '✅ Pembayaran QRIS diterima pada order X.'
        """
        self.ensure_one()
        so_name = self.sale_order_ids[0].name if self.sale_order_ids else self.reference
        return "\u2705 Pembayaran QRIS diterima pada order {order}.".format(
            order=so_name,
        )

    def _whatsapp_build_qris_rejected_text(self, reason=''):
        """Format singkat dengan emoji:
        '❌ Pembayaran QRIS ditolak pada order X. Alasan: ...'
        Alasan opsional ditambahkan kalau ada.
        """
        self.ensure_one()
        so_name = self.sale_order_ids[0].name if self.sale_order_ids else self.reference
        text = "\u274C Pembayaran QRIS ditolak pada order {order}.".format(
            order=so_name,
        )
        # Normalize reason: bisa str, list (dari RPC), atau None
        if isinstance(reason, (list, tuple)):
            reason = ' '.join(str(r) for r in reason if r)
        elif reason is False:
            reason = ''
        if reason:
            text += " Alasan: " + str(reason)
        return text

    def _whatsapp_build_cod_waiting_text(self):
        """Format singkat dengan emoji:
        '📦 Pesanan COD X siap dikirim.'
        """
        self.ensure_one()
        so_name = self.sale_order_ids[0].name if self.sale_order_ids else self.reference
        return "\U0001F4E6 Pesanan COD {order} siap dikirim.".format(
            order=so_name,
        )

    # ============================================================
    # TRIGGER methods (dipanggil dari override atas)
    # ============================================================

    def _whatsapp_notify_qris_pending_verification(self):
        for tx in self:
            text = tx._whatsapp_build_qris_pending_text()
            tx._whatsapp_send_safe('qris_pending_verification', text)

    def _whatsapp_notify_qris_paid(self):
        for tx in self:
            text = tx._whatsapp_build_qris_paid_text()
            tx._whatsapp_send_safe('qris_paid', text)

    def _whatsapp_notify_qris_rejected(self, reason=''):
        for tx in self:
            text = tx._whatsapp_build_qris_rejected_text(reason=reason)
            tx._whatsapp_send_safe('qris_rejected', text)

    def _whatsapp_notify_cod_waiting_delivery(self):
        for tx in self:
            text = tx._whatsapp_build_cod_waiting_text()
            tx._whatsapp_send_safe('cod_waiting_delivery', text)
