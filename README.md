# WhatsApp Evolution API Notification

Odoo 17 module to send automatic WhatsApp notifications to customers via [Evolution API](https://evolution-api.com) when order status changes.

## Triggers Supported

| Trigger | When | Toggle key | Default |
|---|---|---|---|
| `order_received` | Sale order confirmed | `trigger_order_received` | ON |
| `qris_pending_verification` | User clicks "Saya sudah bayar" on QRIS page | `trigger_qris_pending` | OFF (avoid spam) |
| `qris_paid` | Admin verifies QRIS payment | `trigger_qris_paid` | ON |
| `qris_rejected` | Admin rejects QRIS payment | `trigger_qris_rejected` | ON |
| `cod_waiting_delivery` | COD order ready to ship | `trigger_cod_waiting` | ON |
| `order_delivered` | Sale order delivered | `trigger_order_delivered` | ON |
| `order_done` | Sale order done/invoiced | `trigger_order_done` | ON |
| `order_cancelled` | Sale order cancelled | `trigger_order_cancelled` | ON |

## Message Format

### Initial message (order received): includes full detail
```
Halo {name}!

Pesanan Anda di *Warung Lakku* telah kami terima. Berikut detailnya:

No. Order: *S00042*
Tanggal: 18/06/2026 09:30
Metode: QRIS

Item:
- Nasi Goreng x2 (Rp 36.000)
- Es Teh x1 (Rp 5.000)

Total: *Rp 41.000*

Lihat detail pesanan:
https://odoo.warunglakku.com/my/orders/142

Terima kasih telah berbelanja di Warung Lakku.
```

### Subsequent status updates: short format
```
Halo {name},

Update pesanan *S00042* di Warung Lakku:
Status: *Pembayaran Diterima*

Lihat detail: https://odoo.warunglakku.com/my/orders/142

Terima kasih.
```

## Configuration

1. Go to **Settings → Website → WhatsApp Evolution API**
2. Set:
   - **API URL**: `https://evolution.warunglakku.com`
   - **Instance Name**: `Warung Lakku`
   - **API Key**: instance token from Evolution Manager
3. Toggle each trigger on/off as needed
4. Click **Test Connection** (sends a test message to your user's mobile number)

## Phone Number Format

Numbers are auto-normalized to international format:
- `081234567890` → `6281234567890`
- `+62 812-3456-7890` → `6281234567890`
- `6281234567890` → `6281234567890` (unchanged)
- `8123456789` → `628123456789` (assumes Indonesian prefix)

Source: `res_partner.mobile` (fallback to `phone`)

## Audit Log

Every message is logged in `whatsapp.message.log` (menu: **WhatsApp → Message Logs**) with:
- Trigger type, partner, sale order, payment transaction
- Number (raw + normalized)
- Message text + Evolution API response
- Status: success / failed / pending
- Retry count + last retry at

Failed messages are auto-retried every 15 minutes (cron) up to 3 times. Manual retry available via the **Retry Send** button on log form.

Logs older than 90 days are auto-cleaned weekly.

## Dependencies

- `sale_management`
- `website_sale`
- `website_sale_payment_qris_cod` (for QRIS + COD hooks)

## API Reference (Evolution API v2.x)

```http
POST {base_url}/message/sendText/{instance_name}
Header: apikey: {api_key}
Content-Type: application/json

{
  "number": "62xxx",
  "text": "message text",
  "delay": 1200
}
```

Response:
```json
{
  "key": {"remoteJid": "...", "fromMe": true, "id": "..."},
  "status": "PENDING",
  "message": {"conversation": "..."}
}
```

## Author

Warung Lakku — https://warunglakku.com
