# WhatsApp Evolution API Notification

Odoo 17 module to send automatic WhatsApp notifications to customers via [Evolution API](https://evolution-api.com) when order status changes. Designed for restaurant / warung makan workflow with premium, no-emoji, clean modern message format using WhatsApp `*bold*` markdown.

**Current version**: `17.0.1.4.2`

---

## Triggers Supported

| Trigger | When | Toggle key | Default |
|---|---|---|---|
| `order_received` | Sale order confirmed (`state: draft/sent → sale`) | `trigger_order_received` | ON |
| `order_cooking` | `website_order_stage → cooking` | `trigger_order_cooking` | ON |
| `order_delivered` | `website_order_stage → out_for_delivery` | `trigger_order_delivered` | ON |
| `order_done` | `state → done` | `trigger_order_done` | ON |
| `order_cancelled` | `state → cancel` | `trigger_order_cancelled` | ON |
| `cod_waiting_delivery` | COD transaction created | `trigger_cod_waiting` | ON |
| `qris_paid` | Admin verifies QRIS payment | `trigger_qris_paid` | ON |
| `qris_rejected` | Admin rejects QRIS payment (with reason) | `trigger_qris_rejected` | ON |
| `qris_pending_verification` | Customer clicks "Saya sudah bayar" | `trigger_qris_pending` | OFF (avoid spam) |

---

## Message Format (Premium, No Emoji)

### Order Received (full detail)
```
*Warung Lakku*
PESANAN DITERIMA

No. Order : S00024
Tanggal   : 18/06/2026 13:00
Metode    : QRIS

*Item Pesanan*
• Nasi Goreng x2 — Rp 30.000
• Es Teh x1 — Rp 5.000

*Total: Rp 35.000*

Detail pesanan:
https://odoo.warunglakku.com/shop/order/24/abc123-def456
```

### Order Cooking
```
*Pesanan Sedang Dimasak*
Order S00024
```

### Order Out for Delivery
```
*Pesanan Dalam Pengiriman*
Order S00024
```

### Order Done (with feedback URL)
```
*Pesanan Selesai*
Order S00024

Terima kasih telah memesan di Warung Lakku.

Bantu kami meningkatkan layanan:
https://odoo.warunglakku.com/shop/feedback/24/abc123-def456
```

### Order Cancelled
```
*Pesanan Dibatalkan*
Order S00023
```

### QRIS Paid
```
*Pembayaran QRIS Diterima*
Order S00024
```

### QRIS Rejected (with reason)
```
*Pembayaran QRIS Ditolak*
Order S00024

Alasan: Bukti transfer tidak jelas, mohon kirim ulang
```

### COD Waiting Delivery
```
*Pesanan Siap Dikirim*
Order S00024 — COD
```

---

## Public Pages

### `/shop/order/<order_id>/<access_token>` — Read-only order detail
- Public access (no login required), protected by `access_token` field (from `website_sale`)
- Shows: store name, status badge, order number, date, payment method, customer, items table, total
- Read-only notice: no edit/cancel/pay buttons

### `/shop/feedback/<order_id>/<access_token>` — Customer feedback form
- Premium star-rating UI (1-5 stars for **Pengiriman** and **Makanan**)
- Free-text feedback field (max 500 chars)
- Menu request: "Sudah Cukup" / "Ada Usulan Menu Baru" (if "baru", shows textarea for menu suggestion, max 300 chars)
- After submit: thank-you page with summary
- Open URL again: "Penilaian Sudah Diterima" page (1 feedback per order, SQL unique constraint)
- Protected by same `access_token` as order detail page
- POST route uses `csrf=False` (token-based auth via URL)

---

## Admin Backend

### Top-level "Feedback" app menu (sequence 80)
Contains 4 submenus with pre-applied default filters:

| Submenu | Default filter | Use case |
|---|---|---|
| Semua Feedback | (none) | See all feedback records |
| Rating Tinggi (4-5) | `rating_food >= 4 AND rating_delivery >= 4` | Happy customers |
| Rating Rendah (1-2) | `rating_food <= 2 OR rating_delivery <= 2` | Needs follow-up |
| Usulan Menu Baru | `menu_request = 'new'` | Customer menu suggestions |

### "WhatsApp" app menu (sequence 85)
- **Message Logs**: all WA send attempts (success / failed / pending)
- **Configuration**: API settings link

### QA test buttons on sale.order form
- **Kirim WA**: manually trigger `order_received` message
- **Kirim WA (Selesai)**: manually trigger `order_done` message (with feedback URL)

---

## Data Model

### `whatsapp.message.log`
Audit trail of every WA send attempt.

| Field | Description |
|---|---|
| `trigger` | Which trigger fired (order_received, qris_paid, etc.) |
| `partner_id` | Customer (res.partner) |
| `sale_order_id` | Related sale.order |
| `payment_transaction_id` | Related payment.transaction (for QRIS/COD triggers) |
| `number_raw` / `number_normalized` | Phone numbers before/after normalization |
| `message_text` | The exact text sent |
| `message_id` | Evolution API message ID (for tracking) |
| `status` | `pending` / `success` / `failed` |
| `error_message` | Error detail if failed |
| `response_raw` | Full Evolution API response |
| `retry_count` / `last_retry_at` | Retry tracking |
| `company_id` | Multi-company safe |

Failed messages auto-retried every 15 minutes (cron) up to 3 times. Manual retry via **Retry Send** button on log form. Logs older than 90 days auto-cleaned weekly.

### `whatsapp.order.feedback`
Customer feedback submitted via `/shop/feedback/<id>/<token>`.

| Field | Type | Description |
|---|---|---|
| `sale_order_id` | Many2one (unique) | 1 feedback per order |
| `partner_id` | Many2one (related) | Customer (denormalized) |
| `order_name` | Char (related) | Order name for quick view |
| `order_state` | Selection (related) | Order state when feedback submitted |
| `rating_delivery` | Integer (1-5) | Star rating for delivery |
| `rating_food` | Integer (1-5) | Star rating for food |
| `feedback_text` | Text | Free-form feedback (max 500 chars on form) |
| `menu_request` | Selection | `enough` or `new` |
| `menu_request_text` | Text | Menu suggestion (max 300 chars on form, only if `new`) |
| `submitted_at` | Datetime | When feedback was submitted |

SQL constraint: `unique(sale_order_id)` — customer can only submit once per order.

ACL: manager full CRUD / salesman read-only / public create-only (via form).

---

## Configuration

1. Go to **Settings → Website → WhatsApp Evolution API**
2. Set:
   - **API URL**: `https://evolution.warunglakku.com`
   - **Instance Name**: `Warung Lakku`
   - **API Key**: instance token from Evolution Manager
   - **Store Name**: displayed in `order_received` header (default: "Warung Lakku")
   - **Portal Base URL**: base URL for public pages (default: `https://odoo.warunglakku.com`)
3. Toggle each trigger on/off as needed (master switch + per-trigger)
4. Click **Test Connection** (sends a test message to your user's mobile number)

Config params stored in `ir.config_parameter` (prefix: `whatsapp_evolution.*`).

---

## Phone Number Format

Numbers are auto-normalized to international format:
- `081234567890` → `6281234567890`
- `+62 812-3456-7890` → `6281234567890`
- `6281234567890` → `6281234567890` (unchanged)
- `8123456789` → `628123456789` (assumes Indonesian prefix)

Source: `res_partner.mobile` (fallback to `phone`).

---

## Dependencies

- `sale_management`
- `website_sale`
- `website_sale_payment_qris_cod` (for QRIS + COD hooks)

---

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

---

## Module Structure

```
whatsapp_evolution_notification/
├── __init__.py
├── __manifest__.py                          # v17.0.1.4.2
├── README.md
├── controllers/
│   ├── __init__.py
│   └── main.py                              # /shop/order + /shop/feedback routes
├── data/
│   └── ir_cron_retry.xml                    # Cron retry failed messages
├── models/
│   ├── __init__.py
│   ├── whatsapp_message_log.py              # Audit trail model + send logic
│   ├── whatsapp_order_feedback.py           # Feedback model + constraints
│   ├── whatsapp_evolution_client.py         # Evolution API HTTP client (_auto=False)
│   ├── sale_order.py                        # SO hooks + message builders
│   ├── payment_transaction.py               # Payment tx hooks + message builders
│   └── res_config_settings.py               # Settings UI
├── security/
│   └── ir.model.access.csv                  # ACL: log + feedback
├── static/
│   ├── description/icon.png
│   └── src/img/icon.png                     # App menu icon
└── views/
    ├── public_order_views.xml               # Order detail + feedback form/thank-you/already-submitted
    ├── whatsapp_message_log_views.xml       # Admin log list/form/search + WhatsApp menu
    ├── whatsapp_order_feedback_views.xml    # Admin feedback list/form/search + Feedback menu
    ├── sale_order_views.xml                 # QA test buttons on SO form
    └── res_config_settings_views.xml        # Settings UI
```

---

## Changelog

### 17.0.1.4.2
- Fix OwlError on feedback form view (removed `widget="priority"` on Integer fields)

### 17.0.1.4.1
- New top-level app menu **Feedback** (sequence 80) with 4 submenus:
  Semua / Rating Tinggi (4-5) / Rating Rendah (1-2) / Usulan Menu Baru
- Removed duplicate `Order Feedback` submenu under WhatsApp menu

### 17.0.1.4.0
- **New feature: customer feedback form** at `/shop/feedback/<id>/<token>`
- New model `whatsapp.order.feedback` (1 feedback per order, SQL unique constraint)
- New templates: `feedback_form` (premium star-rating UI), `feedback_thankyou`, `feedback_already_submitted`
- `_whatsapp_build_done_text` now appends feedback URL with "Bantu kami meningkatkan layanan"
- New QA button on sale.order: **Kirim WA (Selesai)** to test done_text send
- ACL: manager full / salesman read / public create-only
- 9/9 E2E tests passed with real WA delivery

### 17.0.1.3.0
- **Premium format redesign**: removed all emoji prefixes, switched to `*bold*` WhatsApp markdown
- New trigger: `order_cooking` (`website_order_stage → cooking`)
- Renamed `order_delivered` label: "Pesanan Dikirim" → "Pesanan Dalam Pengiriman"
- Style shifted from courier/package style to restaurant/warung makan style

### 17.0.1.2.0
- Added emoji prefix to all 8 notifications (later removed in v1.3)
- New trigger: `order_delivered` (`website_order_stage → out_for_delivery`)

### 17.0.1.1.0
- Public read-only order detail page at `/shop/order/<id>/<access_token>`
- Removed greetings ("Halo {name}") from all messages — direct to-the-point
- Short status messages for non-initial triggers

### 17.0.1.0.0
- Initial release
- 6 triggers: order_received, qris_pending, qris_paid, qris_rejected, cod_waiting, order_done, order_cancelled
- Evolution API HTTP client with retry
- `whatsapp.message.log` audit trail with cron retry (15 min interval, 3 attempts max)
- Auto-clean logs older than 90 days

---

## Author

Warung Lakku — https://warunglakku.com

## License

LGPL-3
