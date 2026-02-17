from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from oxyde_admin.api.routes import update_record


@pytest.mark.asyncio
class TestUpdateRecord:
    async def test_update_record_filters_readonly(self, MockUser):
        record = MagicMock()
        record.save = AsyncMock()
        MockUser.objects.get = AsyncMock(return_value=record)

        data = {
            "id": 99,
            "name": "New Name",
            "email": "new@test.com",
            "is_active": False,
        }
        await update_record(MockUser, 1, data, readonly_fields=["email"])

        # email is readonly, id is PK — both should be blocked
        record.save.assert_awaited_once()
        save_fields = record.save.call_args[1]["update_fields"]
        assert "email" not in save_fields
        assert "id" not in save_fields
        assert "name" in save_fields
        assert "is_active" in save_fields

    async def test_update_record_filters_pk(self, MockUser):
        record = MagicMock()
        record.save = AsyncMock()
        MockUser.objects.get = AsyncMock(return_value=record)

        data = {"id": 99, "name": "Updated"}
        await update_record(MockUser, 1, data)

        save_fields = record.save.call_args[1]["update_fields"]
        assert "id" not in save_fields
        assert "name" in save_fields

    async def test_update_record_no_readonly(self, MockUser):
        record = MagicMock()
        record.save = AsyncMock()
        MockUser.objects.get = AsyncMock(return_value=record)

        data = {"name": "Updated", "email": "up@test.com"}
        await update_record(MockUser, 1, data)

        save_fields = record.save.call_args[1]["update_fields"]
        assert "name" in save_fields
        assert "email" in save_fields
