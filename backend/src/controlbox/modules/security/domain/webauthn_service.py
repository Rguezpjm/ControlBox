import base64
import json
from uuid import UUID

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from controlbox.config.settings import Settings
from controlbox.modules.security.domain.entities import WebAuthnCredential
from controlbox.modules.security.domain.services import WebAuthnChallengeStore
from controlbox.shared.domain.base import utc_now


class WebAuthnService:
    def __init__(self, settings: Settings, challenge_store: WebAuthnChallengeStore) -> None:
        self._settings = settings
        self._challenges = challenge_store

    async def registration_options(self, user_id: UUID, email: str, existing: list[WebAuthnCredential]) -> dict:
        exclude = [
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
            for c in existing
        ]
        options = generate_registration_options(
            rp_id=self._settings.webauthn_rp_id,
            rp_name=self._settings.webauthn_rp_name,
            user_id=str(user_id).encode(),
            user_name=email,
            user_display_name=email,
            exclude_credentials=exclude,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )
        challenge_b64 = bytes_to_base64url(options.challenge)
        await self._challenges.store(challenge_b64, {"user_id": str(user_id), "type": "registration"})
        return json.loads(options.model_dump_json())

    async def verify_registration(
        self,
        user_id: UUID,
        credential: dict,
        nickname: str = "Passkey",
    ) -> WebAuthnCredential:
        client_data = _decode_client_data(credential)
        challenge = client_data.get("challenge", "")
        stored = await self._challenges.consume(challenge)
        if stored is None or stored.get("user_id") != str(user_id):
            raise ValueError("Invalid or expired challenge")

        verification = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=self._settings.webauthn_rp_id,
            expected_origin=self._settings.webauthn_origin,
        )
        return WebAuthnCredential(
            user_id=user_id,
            credential_id=bytes_to_base64url(verification.credential_id),
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            transports=credential.get("transports", []),
            nickname=nickname,
        )

    async def authentication_options(self, user_id: UUID, credentials: list[WebAuthnCredential]) -> dict:
        allow = [
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id), transports=c.transports)
            for c in credentials
        ]
        options = generate_authentication_options(
            rp_id=self._settings.webauthn_rp_id,
            allow_credentials=allow,
            user_verification=UserVerificationRequirement.PREFERRED,
        )
        challenge_b64 = bytes_to_base64url(options.challenge)
        await self._challenges.store(challenge_b64, {"user_id": str(user_id), "type": "authentication"})
        return json.loads(options.model_dump_json())

    async def verify_authentication(self, credential: dict, stored: WebAuthnCredential) -> WebAuthnCredential:
        client_data = _decode_client_data(credential)
        challenge = client_data.get("challenge", "")
        stored_challenge = await self._challenges.consume(challenge)
        if stored_challenge is None:
            raise ValueError("Invalid or expired challenge")

        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=self._settings.webauthn_rp_id,
            expected_origin=self._settings.webauthn_origin,
            credential_public_key=stored.public_key,
            credential_current_sign_count=stored.sign_count,
        )
        stored.sign_count = verification.new_sign_count
        stored.last_used_at = utc_now()
        stored.touch()
        return stored


def _decode_client_data(credential: dict) -> dict:
    client_data_b64 = credential.get("response", {}).get("clientDataJSON", "")
    if not client_data_b64:
        raise ValueError("Missing clientDataJSON")
    padded = client_data_b64 + "=" * ((4 - len(client_data_b64) % 4) % 4)
    return json.loads(base64.urlsafe_b64decode(padded).decode())
