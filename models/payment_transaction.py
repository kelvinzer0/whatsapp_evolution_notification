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
        res = super().action_qris_user_confirm_paid()
        for tx in self:
            if tx.qris_state == 'pending_verification':
                try:
                    tx._whatsapp_notify_qris_pending_verification()
                except Exception as e:
                    _logger.exception("[WA] Failed notify qris_pending_verification for %s: %s",
                                      tx.reference, e)
        return res

    def action_qris_mark_paid(self, mutation_record=None):
        """Admin verify -> state paid."""
        res = super().action_qris_mark_paid(mutation_record=mutation_record)
        for tx in self:
            if tx.qris_state == 'paid':
                try:
                    tx._whatsapp_notify_qris_paid()
                except Exception as e:
                    _logger.exception("[WA] Failed notify qris_paid for %s: %s",
                                      tx.reference, e)
        return res

    def action_qris_reject(self, reason=''):
        """Admin reject -> state rejected."""
        res = super().action_qris_reject(reason=reason)
        for tx in self:
            if tx.qris_state == 'rejected':
                try:
                    tx._whatsapp_notify_qris_rejected(reason=reason)
                except Exception as e:
                    _logger.exception("[WA] Failed notify qris_rejected for %s: %s",
                                      tx.reference, e)
        return res

    def action_cod_mark_delivered(self):
        """Admin mark COD delivered."""
        res = super().action_cod_mark_delivered()
        for tx in self:
            if tx.cod_state == 'delivered':
                try:
                    tx._whatsapp_notify_cod_waiting_delivery()
                except Exception as e:
                    _logger.exception("[WA] Failed notify cod_delivered for %s: %s",
                                      tx.reference, e)
        return res

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
        """URL portal customer untuk sale order terkait."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        base = (ICP.get_param('whatsapp_evolution.portal_base_url')
                or 'https://odoo.warunglakku.com').rstrip('/')
        if self.sale_order_ids:
            return '%s/my/orders/%d' % (base, self.sale_order_ids[0].id)
        return base + '/my/orders'

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
        self.ensure_one()
        store = self._whatsapp_get_store_name()
        url = self._whatsapp_get_portal_url()
        partner_name = (self.partner_id.name
                        or (self.sale_order_ids[0].partner_id.name if self.sale_order_ids else '')
                        or 'Pelanggan')
        so_name = self.sale_order_ids[0].name if self.sale_order_ids else self.reference
        text = (
            "Halo {name},\n\n"
            "Terima kasih, konfirmasi pembayaran QRIS untuk pesanan *{order}* telah kami terima.\n"
            "Status: *Menunggu Verifikasi Admin* (estimasi ~5-15 menit)\n\n"
            "Lihat detail: {url}\n\n"
            "Terima kasih atas kesabaran Anda."
        ).format(
            name=partner_name,
            order=so_name,
            url=url,
        )
        return text

    def _whatsapp_build_qris_paid_text(self):
        self.ensure_one()
        store = self._whatsapp_get_store_name()
        url = self._whatsapp_get_portal_url()
        partner_name = (self.partner_id.name
                        or (self.sale_order_ids[0].partner_id.name if self.sale_order_ids else '')
                        or 'Pelanggan')
        so_name = self.sale_order_ids[0].name if self.sale_order_ids else self.reference
        text = (
            "Halo {name},\n\n"
            "Pembayaran QRIS untuk pesanan *{order}* telah *DIVERIFIKASI*.\n"
            "Status: *Pembayaran Diterima* - pesanan Anda akan segera kami proses.\n\n"
            "Lihat detail: {url}\n\n"
            "Terima kasih telah berbelanja di {store}."
        ).format(
            name=partner_name,
            order=so_name,
            url=url,
            store=store,
        )
        return text

    def _whatsapp_build_qris_rejected_text(self, reason=''):
        self.ensure_one()
        store = self._whatsapp_get_store_name()
        url = self._whatsapp_get_portal_url()
        partner_name = (self.partner_id.name
                        or (self.sale_order_ids[0].partner_id.name if self.sale_order_ids else '')
                        or 'Pelanggan')
        so_name = self.sale_order_ids[0].name if self.sale_order_ids else self.reference
        reason_text = ('Alasan: ' + reason) if reason else ''
        text = (
            "Halo {name},\n\n"
            "Mohon maaf, pembayaran QRIS untuk pesanan *{order}* *DITOLAK* oleh admin.\n"
            "{reason}\n\n"
            "Silakan ulangi pembayaran atau hubungi kami untuk bantuan.\n"
            "Lihat detail: {url}\n\n"
            "Terima kasih."
        ).format(
            name=partner_name,
            order=so_name,
            reason=reason_text,
            url=url,
        )
        return text

    def _whatsapp_build_cod_waiting_text(self):
        self.ensure_one()
        store = self._whatsapp_get_store_name()
        url = self._whatsapp_get_portal_url()
        partner_name = (self.partner_id.name
                        or (self.sale_order_ids[0].partner_id.name if self.sale_order_ids else '')
                        or 'Pelanggan')
        so_name = self.sale_order_ids[0].name if self.sale_order_ids else self.reference
        text = (
            "Halo {name},\n\n"
            "Pesanan COD *{order}* sedang kami siapkan dan akan segera dikirim.\n"
            "Status: *Siap Dikirim (COD)*\n"
            "Pastikan Anda menyiapkan uang tunai sesuai total pesanan.\n\n"
            "Lihat detail: {url}\n\n"
            "Terima kasih."
        ).format(
            name=partner_name,
            order=so_name,
            url=url,
        )
        return text

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
