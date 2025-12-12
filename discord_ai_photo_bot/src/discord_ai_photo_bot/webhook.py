"""Webhook endpoint for BTC payment confirmations."""

import hmac
import hashlib
import json
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from .config import Settings
from .payments.bitcoin import BitcoinPaymentGateway


class PaymentWebhookPayload(BaseModel):
    """Payload for BTC payment webhook."""

    invoice_id: str
    status: str
    amount_btc: Optional[float] = None
    tx_hash: Optional[str] = None
    error_message: Optional[str] = None


def create_webhook_app(settings: Settings, payments: BitcoinPaymentGateway) -> FastAPI:
    """Create FastAPI app with BTC payment webhook endpoint."""

    app = FastAPI(title="Discord AI Photo Bot Webhook", version="1.0.0")

    async def verify_and_parse_webhook(request: Request) -> PaymentWebhookPayload:
        """Verify webhook signature and parse payload."""
        body_bytes = await request.body()

        # Always verify signature - security requirement
        if not settings.payment_webhook_secret:
            raise HTTPException(
                status_code=500,
                detail="Webhook signature verification required but secret not configured"
            )

        signature = request.headers.get("X-Signature")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing webhook signature")

        expected_signature = hmac.new(
            settings.payment_webhook_secret.encode(),
            body_bytes,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        # Parse JSON payload
        try:
            body_json = json.loads(body_bytes.decode("utf-8"))
            return PaymentWebhookPayload(**body_json)
        except (json.JSONDecodeError, ValidationError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")

    @app.post("/webhook/btc-payment")
    async def btc_payment_webhook(
        payload: PaymentWebhookPayload = Depends(verify_and_parse_webhook)
    ) -> JSONResponse:
        """
        Handle BTC payment confirmations with enhanced error handling.

        Expected payload:
        {
            "invoice_id": "uuid-string",
            "status": "confirmed" | "failed" | "pending",
            "amount_btc": 0.00123456,
            "tx_hash": "bitcoin-tx-hash",
            "error_message": "optional error description"
        }
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            invoice_id = payload.invoice_id
            status = payload.status

            # Validate invoice_id format (basic UUID check)
            if not invoice_id or len(invoice_id) < 10:
                logger.warning(f"Invalid invoice_id format: {invoice_id}")
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Invalid invoice_id format"}
                )

            logger.info(f"Processing webhook for invoice {invoice_id}, status: {status}")

            if status == "confirmed":
                payments.mark_confirmed(invoice_id)
                response_data = {
                    "status": "ok",
                    "message": f"Payment {invoice_id} confirmed",
                    "invoice_id": invoice_id,
                    "confirmation_time": "now"
                }
                if payload.tx_hash:
                    response_data["tx_hash"] = payload.tx_hash
                return JSONResponse(content=response_data)

            elif status == "failed":
                logger.warning(f"Payment failed for invoice {invoice_id}: {payload.error_message}")
                response_data = {
                    "status": "failed",
                    "message": f"Payment {invoice_id} failed",
                    "invoice_id": invoice_id,
                    "error": payload.error_message or "Payment failed"
                }
                return JSONResponse(content=response_data)

            elif status == "pending":
                logger.info(f"Payment pending for invoice {invoice_id}")
                return JSONResponse(
                    content={
                        "status": "pending",
                        "message": f"Payment {invoice_id} still pending",
                        "invoice_id": invoice_id
                    }
                )

            else:
                logger.warning(f"Unhandled payment status: {status} for invoice {invoice_id}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": f"Unhandled status: {status}",
                        "supported_statuses": ["confirmed", "failed", "pending"]
                    }
                )

        except Exception as e:
            logger.exception(f"Error processing webhook: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": "Internal server error",
                    "invoice_id": payload.invoice_id if payload else "unknown"
                }
            )

    @app.get("/health")
    async def health_check() -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse(content={"status": "healthy"})

    return app



