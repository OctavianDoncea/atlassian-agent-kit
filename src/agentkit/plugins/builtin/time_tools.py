from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, Field
from agentkit.plugins.base import IntegrationPlugin, ToolSpec

class CurrentTimeInput(BaseModel):
    timezone: str = Field('UTC', description='IANA timezone name, e.g. "America/New_York"')


class ConvertTimeInput(BaseModel):
    iso_timestamp: str = Field(description='ISO 8601 timestamp without offset, e.g. "2026-10-27T12:00:00Z"')
    from_timezone: str = Field('UTC', description='IANA timezone of the input timestamp')
    to_timezone: str = Field(description='Target IANA timezone')


class TimeToolsPlugin(IntegrationPlugin):
    name = 'time'
    display_name = 'Time & Timezones'
    version = '1.0.0'

    def current_time(self, inp: CurrentTimeInput) -> dict:
        try:
            now = datetime.now(ZoneInfo(inp.timezone))
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f'unknown timezone {inp.timezone!r}') from exc
        
        return {'timezone': inp.timezone, 'iso': now.isoformat()}

    def convert_time(self, inp: ConvertTimeInput) -> dict:
        dt = datetime.fromisoformat(inp.iso_timestamp).replace(tzinfo=ZoneInfo(inp.from_timezone))
        converted = dt.astimezone(ZoneInfo(inp.to_timezone))

        return {'timezone': inp.to_timezone, 'iso': converted.isoformat()}

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec('get_current_time', 'Get the current date and time in an IANA timezone.', CurrentTimeInput, lambda c, i: c.current_time(i)),
            ToolSpec('convert_timezone', 'Convert an ISO timestamp from one IANA timezone', ConvertTimeInput, lambda c, i: c.convert_time(i))
        ]
