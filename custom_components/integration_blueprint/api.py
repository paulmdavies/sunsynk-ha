"""Sample API Client."""

from __future__ import annotations

import asyncio
import base64
import socket
import time
from io import StringIO
from typing import Any

import aiohttp
import async_timeout
import requests
from aiohttp import ClientSession
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.serialization import load_pem_public_key


class IntegrationBlueprintApiClientError(Exception):
    """Exception to indicate a general API error."""


class IntegrationBlueprintApiClientCommunicationError(
    IntegrationBlueprintApiClientError,
):
    """Exception to indicate a communication error."""


class IntegrationBlueprintApiClientAuthenticationError(
    IntegrationBlueprintApiClientError,
):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise IntegrationBlueprintApiClientAuthenticationError(
            msg,
        )
    response.raise_for_status()


class IntegrationBlueprintApiClient:
    """Sample API Client."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Sample API Client."""
        self._username = username
        self._password = password
        self._session = session
        self._token = None

    async def _get_token(self, username: str, password: str):
        # Get key to encode token with
        response_json = await self._api_wrapper(
            method='get',
            url='https://api.sunsynk.net/anonymous/publicKey',
            params={
                'source': 'sunsynk',
                'nonce': int(time.time() * 1000)
            },
            token_required=False,
        )

        # Write public key file
        public_key_file = StringIO()
        public_key_file.writelines(
            [
                '-----BEGIN PUBLIC KEY-----',
                response_json['data'],
                '-----END PUBLIC KEY-----'
            ]
        )
        public_key_file.seek(0)

        # Load public key
        public_key = load_pem_public_key(
            bytes(public_key_file.read(), encoding='utf-8'),
        )

        encrypted_password = base64.b64encode(public_key.encrypt(
            password.encode('utf-8'),
            padding=PKCS1v15()
        )).decode('utf-8')

        # API URL
        url = f'https://api.sunsynk.net/oauth/token/new'
        # Prepare request payload
        payload = {
            "areaCode": "sunsynk",
            "client_id": "csp-web",
            "grant_type": "password",
            "password": encrypted_password,
            "source": "sunsynk",
            "username": username
        }
        # Headers
        headers = {"Content-Type": "application/json"}
        try:
            # Send POST request with timeout (10s)
            # response = requests.post(url, json=payload, headers=headers, timeout=10)
            # response.raise_for_status()
            response_json = await self._api_wrapper(
                'post',
                url,
                data=payload,
                headers=headers,
                token_required=False,
            )

            return response_json['data']['access_token']
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")

    async def async_get_data(self) -> Any:
        """Get data from the API."""
        return await self._api_wrapper(
            method="get",
            url="https://api.sunsynk.net/api/v1/inverter/2407291419",
        )

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
        token_required: bool = True,
    ) -> Any:
        """Get information from the API."""
        if token_required and not self._token:
            self._token = await self._get_token(self._username, self._password)
            print(f"Token: {self._token}")
        try:
            async with async_timeout.timeout(10):
                if token_required:
                    headers = headers or {}
                    headers["Authorization"] = f"Bearer {self._token}"
                response = await self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    json=data,
                )
                _verify_response_or_raise(response)
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise IntegrationBlueprintApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise IntegrationBlueprintApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise IntegrationBlueprintApiClientError(
                msg,
            ) from exception


async def main():
    data = await asyncio.ensure_future(IntegrationBlueprintApiClient('paulmdavies@gmail.com', 'FKUG2Uv8Z2yE!DSv', ClientSession()).async_get_data())  # fire and forget async_foo()
    print(data)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())